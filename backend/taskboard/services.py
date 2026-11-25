"""What people do with tasks and projects.

Every action checks who may do it and raises ``TaskError`` (with an HTTP
status) when they may not, so endpoints stay thin.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from groups.models import UserCommunityStatus
from taskboard.models import (
    Project,
    ProjectStage,
    ProjectTemplate,
    ProjectUpdate,
    Task,
    TaskComment,
    TaskPreferences,
    TeamKind,
    Weight,
)
from taskboard.teams import Membership, can_assign

SNOOZE = timedelta(days=7)


class TaskError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def preferences(user) -> TaskPreferences:
    prefs, _ = TaskPreferences.objects.get_or_create(user=user)
    return prefs


def is_paused(user) -> bool:
    """A pilot's tasks pause while they say so or are On Leave or alumni."""
    if TaskPreferences.objects.filter(user=user, paused=True).exists():
        return True
    return UserCommunityStatus.objects.filter(
        user=user, status__in=UserCommunityStatus.AWAY_STATUSES
    ).exists()


def can_see(user, task: Task, membership: Optional[Membership] = None) -> bool:
    if user.pk in (task.user_id, task.created_by_id):
        return True
    if user.is_superuser:
        return True
    if task.project_id and task.project.lead_id == user.pk:
        return True
    if task.team_kind:
        membership = membership or Membership(user)
        return membership.can_act(task.team_kind, task.team_id, task.team_role)
    return False


def _touch(task: Task, now, *fields: str) -> None:
    task.last_activity_at = now
    task.still_needed_asked_at = None
    task.save(
        update_fields=sorted(
            set(fields) | {"last_activity_at", "still_needed_asked_at"}
        )
    )


def _own(user, task: Task) -> None:
    if task.user_id != user.pk:
        raise TaskError("This isn't your task.", 403)
    if task.status != Task.STATUS_OPEN:
        raise TaskError("This task is closed.")


def mark_done(user, task: Task) -> Task:
    """Assigned tasks only: automatic ones close when the thing is fixed."""
    _own(user, task)
    if task.kind == Task.KIND_AUTOMATIC and not task.team_kind:
        raise TaskError("This one closes by itself once it's fixed.")
    now = timezone.now()
    with transaction.atomic():
        task.status = Task.STATUS_DONE
        task.closed_at = now
        task.close_note = "Marked done"
        _touch(task, now, "status", "closed_at", "close_note")
        _open_next_copy(task, now)
    return task


def _open_next_copy(task: Task, now) -> Optional[Task]:
    """A repeating task opens its next copy when this one closes.

    Only one copy is ever open, so a missed week never stacks up.
    """
    if not task.recurrence.startswith("weekly:"):
        return None
    weekday = int(task.recurrence.split(":", 1)[1])
    today = timezone.localdate(now)
    start = max(today, task.due_date or today) + timedelta(days=1)
    due = start + timedelta(days=(weekday - start.weekday()) % 7)
    project = task.project
    if project and project.status != Project.STATUS_OPEN:
        return None
    if project and project.target_date and due > project.target_date:
        return None
    return Task.objects.create(
        kind=task.kind,
        title=task.title,
        detail=task.detail,
        body=task.body,
        link_url=task.link_url,
        link_label=task.link_label,
        weight=task.weight,
        user_id=None if task.team_kind else task.user_id,
        team_kind=task.team_kind,
        team_id=task.team_id,
        team_role=task.team_role,
        team_label=task.team_label,
        project=project,
        stage=task.stage,
        when=Task.WHEN_DATE,
        due_date=due,
        recurrence=task.recurrence,
        opened_at=now,
        last_activity_at=now,
        created_by=task.created_by,
    )


def snooze(user, task: Task) -> Task:
    _own(user, task)
    now = timezone.now()
    task.snoozed_until = now + SNOOZE
    _touch(task, now, "snoozed_until")
    return task


def not_now(user, task: Task) -> Task:
    """Suggestions: stop asking until the pilot brings it back."""
    _own(user, task)
    if task.weight != Weight.SUGGESTION:
        raise TaskError("Only suggestions can be put aside.")
    now = timezone.now()
    task.status = Task.STATUS_STOPPED
    task.closed_at = now
    task.close_note = "You said not now"
    _touch(task, now, "status", "closed_at", "close_note")
    return task


def bring_back(user, task: Task) -> Task:
    if task.user_id != user.pk:
        raise TaskError("This isn't your task.", 403)
    if task.status != Task.STATUS_STOPPED:
        raise TaskError("Only tasks that stopped asking come back.")
    now = timezone.now()
    task.status = Task.STATUS_OPEN
    task.opened_at = now
    task.closed_at = None
    task.close_note = ""
    _touch(task, now, "status", "opened_at", "closed_at", "close_note")
    return task


def hand_back(user, task: Task) -> Task:
    """Give an assigned or taken task back to whoever it came from."""
    _own(user, task)
    now = timezone.now()
    if task.team_kind:
        task.user = None
        task.claimed_at = None
        _touch(task, now, "user", "claimed_at")
        return task
    if task.kind != Task.KIND_ASSIGNED:
        raise TaskError("This one closes by itself once it's fixed.")
    if task.created_by_id and task.created_by_id != user.pk:
        task.user_id = task.created_by_id
        task.detail = f"{user.username} handed it back"
        _touch(task, now, "user", "detail")
        return task
    task.status = Task.STATUS_CANCELLED
    task.closed_at = now
    task.close_note = "Handed back"
    _touch(task, now, "status", "closed_at", "close_note")
    return task


def take(user, task: Task, membership: Optional[Membership] = None) -> Task:
    if task.status != Task.STATUS_OPEN or not task.team_kind:
        raise TaskError("Only open team tasks can be taken.")
    if task.user_id:
        raise TaskError("Someone already took this.", 409)
    membership = membership or Membership(user)
    if not membership.can_act(task.team_kind, task.team_id, task.team_role):
        raise TaskError("This task belongs to another team.", 403)
    now = timezone.now()
    task.user = user
    task.claimed_at = now
    _touch(task, now, "user", "claimed_at")
    return task


def keep(user, task: Task) -> Task:
    """The author says an untouched assigned task is still needed."""
    if task.created_by_id != user.pk and not user.is_superuser:
        raise TaskError("Only whoever made it can keep it.", 403)
    _touch(task, timezone.now())
    return task


def let_close(user, task: Task) -> Task:
    if task.created_by_id != user.pk and not user.is_superuser:
        raise TaskError("Only whoever made it can close it.", 403)
    now = timezone.now()
    task.status = Task.STATUS_CANCELLED
    task.closed_at = now
    task.close_note = "No longer needed"
    _touch(task, now, "status", "closed_at", "close_note")
    return task


def thank(user, task: Task) -> Task:
    if task.status != Task.STATUS_DONE or not task.user_id:
        raise TaskError("Thanks go to finished tasks.")
    if task.user_id == user.pk:
        raise TaskError("You can't thank yourself.")
    if task.thanked_at:
        return task
    task.thanked_by = user
    task.thanked_at = timezone.now()
    task.save(update_fields=["thanked_by", "thanked_at"])
    return task


ACTIONS = {
    "done": mark_done,
    "snooze": snooze,
    "not_now": not_now,
    "bring_back": bring_back,
    "hand_back": hand_back,
    "take": take,
    "keep": keep,
    "let_close": let_close,
    "thank": thank,
}


def comment(user, task: Task, body: str) -> TaskComment:
    body = (body or "").strip()
    if not body:
        raise TaskError("Write something first.")
    if not can_see(user, task):
        raise TaskError("Task not found.", 404)
    now = timezone.now()
    note = TaskComment.objects.create(task=task, author=user, body=body[:2000])
    if task.status == Task.STATUS_OPEN:
        _touch(task, now)
    return note


def create_task(
    user,
    *,
    title: str,
    assignee: Optional[User] = None,
    screen: str = "",
    when: str = Task.WHEN_THIS_WEEK,
    due_date: Optional[date] = None,
    body: str = "",
    link_url: str = "",
    project: Optional[Project] = None,
    stage: Optional[ProjectStage] = None,
) -> Task:
    if not can_assign(user):
        raise TaskError("Only leaders can give out tasks.", 403)
    title = (title or "").strip()
    if not title:
        raise TaskError("Say what needs doing.")
    if not assignee and not screen:
        raise TaskError("Pick who does it.")
    if when == Task.WHEN_DATE and not due_date:
        raise TaskError("Pick the date.")
    if when != Task.WHEN_DATE:
        due_date = None
    if project and not can_edit_project(user, project):
        raise TaskError("Only the project lead adds tasks to it.", 403)
    if stage and stage.project_id != getattr(project, "pk", None):
        raise TaskError("That stage is in another project.")
    now = timezone.now()
    return Task.objects.create(
        kind=Task.KIND_ASSIGNED,
        title=title[:200],
        body=body[:4000],
        link_url=link_url[:500],
        user=assignee,
        team_kind=TeamKind.STAFF if screen and not assignee else "",
        team_role=screen if not assignee else "",
        when=when,
        due_date=due_date,
        project=project,
        stage=stage,
        opened_at=now,
        last_activity_at=now,
        created_by=user,
        detail=f"{user.username} asked" if assignee != user else "",
    )


# --- Projects -----------------------------------------------------------


def can_edit_project(user, project: Project) -> bool:
    return user.is_superuser or project.lead_id == user.pk


def create_project(
    user,
    *,
    name: str,
    lead: User,
    template: Optional[ProjectTemplate] = None,
    starts_on: Optional[date] = None,
    target_date: Optional[date] = None,
    link_url: str = "",
) -> Project:
    if not can_assign(user):
        raise TaskError("Only leaders start projects.", 403)
    name = (name or "").strip()
    if not name:
        raise TaskError("Name the project.")
    starts_on = starts_on or timezone.localdate()
    now = timezone.now()
    with transaction.atomic():
        project = Project.objects.create(
            name=name[:120],
            template=template,
            lead=lead,
            starts_on=starts_on,
            target_date=target_date,
            link_url=link_url[:500],
            created_by=user,
        )
        if template is None:
            ProjectStage.objects.create(project=project, name="Tasks")
            return project
        stages: dict[str, ProjectStage] = {}
        for row in template.tasks.all():
            stage = stages.get(row.stage)
            if stage is None:
                stage = ProjectStage.objects.create(
                    project=project, name=row.stage, position=len(stages)
                )
                stages[row.stage] = stage
            due = (
                starts_on + timedelta(days=row.offset_days)
                if row.offset_days is not None
                else None
            )
            if due and due < timezone.localdate():
                # A project started late doesn't open with overdue tasks.
                due = timezone.localdate()
            if row.recurrence.startswith("weekly:"):
                weekday = int(row.recurrence.split(":", 1)[1])
                first = max(starts_on, due or starts_on)
                due = first + timedelta(days=(weekday - first.weekday()) % 7)
            screen = (
                row.goes_to.split(":", 1)[1]
                if row.goes_to.startswith("screen:")
                else ""
            )
            Task.objects.create(
                kind=Task.KIND_ASSIGNED,
                title=row.title,
                user=None if screen else lead,
                team_kind=TeamKind.STAFF if screen else "",
                team_role=screen,
                project=project,
                stage=stage,
                when=Task.WHEN_DATE if due else Task.WHEN_NO_RUSH,
                due_date=due,
                recurrence=row.recurrence,
                opened_at=now,
                last_activity_at=now,
                created_by=user,
            )
    return project


def post_update(user, project: Project, health: str, body: str):
    if not can_edit_project(user, project):
        raise TaskError("Only the project lead posts updates.", 403)
    if health not in dict(ProjectUpdate.HEALTH_CHOICES):
        raise TaskError("Pick on track, at risk or off track.")
    body = (body or "").strip()
    if not body:
        raise TaskError("Say what changed.")
    return ProjectUpdate.objects.create(
        project=project, author=user, health=health, body=body[:4000]
    )


def finish_project(user, project: Project) -> Project:
    if not can_edit_project(user, project):
        raise TaskError("Only the project lead finishes it.", 403)
    now = timezone.now()
    with transaction.atomic():
        project.status = Project.STATUS_FINISHED
        project.finished_at = now
        project.save(update_fields=["status", "finished_at"])
        project.tasks.filter(status=Task.STATUS_OPEN).update(
            status=Task.STATUS_CANCELLED,
            closed_at=now,
            close_note="The project finished",
        )
    return project
