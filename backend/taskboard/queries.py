"""The read side: My tasks, the Team tab and projects, as plain dicts.

Endpoints validate these with Ninja schemas (``taskboard.schemas``).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Iterable, Optional

from django.db.models import Count, Q
from django.utils import timezone

from django.contrib.auth.models import User

from eveonline.helpers.characters.identity import primary_refs_for_users
from eveonline.models import EveCorporation, EvePlayer
from groups.models import UserCommunityStatus
from manage_hub.screens import SCREENS
from tribes.helpers.chiefs import group_seats
from tribes.models import Tribe, TribeGroup, TribeGroupMembership
from taskboard.models import (
    Project,
    ProjectTemplate,
    ProjectUpdate,
    Task,
    TaskPreferences,
    TeamKind,
    Weight,
)
from taskboard.reminders import can_remind, wants_reminders
from taskboard.rules import RULES
from taskboard.services import can_edit_project, is_paused
from taskboard.teams import Membership, can_assign

# Automatic needs-you tasks move to "Now" after waiting this long.
NOW_AFTER = timedelta(days=3)
WEEK = timedelta(days=7)
STOPPED_SHOWN_FOR = timedelta(days=30)


def people(user_ids: Iterable[int]) -> dict[int, dict]:
    """User id -> {user_id, name, character_id} named by their main."""

    ids = {uid for uid in user_ids if uid}
    if not ids:
        return {}
    refs = primary_refs_for_users(ids)
    names = dict(User.objects.filter(pk__in=ids).values_list("pk", "username"))
    result = {}
    for uid in ids:
        character_id, character_name = refs.get(uid, (None, ""))
        result[uid] = {
            "user_id": uid,
            "name": character_name or names.get(uid, ""),
            "character_id": character_id,
        }
    return result


def _actions(task: Task, viewer, membership: Membership) -> list[str]:
    actions = []
    mine = task.user_id == viewer.pk
    if task.status == Task.STATUS_OPEN:
        if mine:
            if task.kind == Task.KIND_ASSIGNED or task.team_kind:
                actions.append("done")
            actions.append("snooze")
            if task.weight == Weight.SUGGESTION:
                actions.append("not_now")
            if task.kind == Task.KIND_ASSIGNED or task.team_kind:
                actions.append("hand_back")
        elif task.team_kind and not task.user_id:
            if membership.can_act(
                task.team_kind, task.team_id, task.team_role
            ):
                actions.append("take")
        if task.still_needed_asked_at and (
            task.created_by_id == viewer.pk or viewer.is_superuser
        ):
            actions += ["keep", "let_close"]
    elif task.status == Task.STATUS_STOPPED and mine:
        actions.append("bring_back")
    elif (
        task.status == Task.STATUS_DONE
        and task.user_id
        and not mine
        and not task.thanked_at
    ):
        actions.append("thank")
    return actions


def serialize_tasks(tasks: list[Task], viewer, membership=None) -> list[dict]:
    membership = membership or Membership(viewer)
    who = people(
        uid
        for task in tasks
        for uid in (task.user_id, task.created_by_id, task.thanked_by_id)
    )
    comment_counts = dict(
        Task.objects.filter(pk__in=[task.pk for task in tasks])
        .annotate(n=Count("comments"))
        .values_list("pk", "n")
    )
    rows = []
    for task in tasks:
        rows.append(
            {
                "id": task.pk,
                "kind": task.kind,
                "rule": task.rule,
                "title": task.title,
                "detail": task.detail,
                "body": task.body,
                "link_url": task.link_url,
                "link_label": task.link_label,
                "weight": task.weight,
                "status": task.status,
                "when": task.when,
                "due_date": task.due_date,
                "recurrence": task.recurrence,
                "opened_at": task.opened_at,
                "closed_at": task.closed_at,
                "close_note": task.close_note,
                "snoozed_until": task.snoozed_until,
                "assignee": who.get(task.user_id),
                "created_by": who.get(task.created_by_id),
                "thanked_by": who.get(task.thanked_by_id),
                "team_kind": task.team_kind,
                "team_id": task.team_id,
                "team_role": task.team_role,
                "team_label": task.team_label or _team_label(task),
                "project_id": task.project_id,
                "project_name": task.project.name if task.project_id else "",
                "stage": task.stage.name if task.stage_id else "",
                "waiting_on": (
                    {"id": task.waiting_on_id, "title": task.waiting_on.title}
                    if task.waiting_on_id
                    else None
                ),
                "still_needed": bool(task.still_needed_asked_at),
                "comment_count": comment_counts.get(task.pk, 0),
                "actions": _actions(task, viewer, membership),
            }
        )
    return rows


def _team_label(task: Task) -> str:
    if task.team_kind == TeamKind.STAFF:

        for screen in SCREENS:
            if screen.key == task.team_role:
                return screen.key.replace("_", " ").capitalize()
    return ""


def _related(queryset):
    return queryset.select_related("project", "stage", "waiting_on").order_by(
        "due_date", "opened_at", "id"
    )


def my_tasks(user) -> dict:
    now = timezone.now()
    today = timezone.localdate(now)
    prefs = TaskPreferences.objects.filter(user=user).first()
    show_suggestions = prefs.show_suggestions if prefs else True
    paused = is_paused(user)
    membership = Membership(user)

    open_mine = list(
        _related(
            Task.objects.filter(user=user, status=Task.STATUS_OPEN).filter(
                Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=now)
            )
        )
    )
    snoozed = Task.objects.filter(
        user=user, status=Task.STATUS_OPEN, snoozed_until__gt=now
    ).count()

    groups = {"now": [], "week": [], "later": [], "minute": []}
    for task in open_mine:
        if task.weight == Weight.SUGGESTION:
            if show_suggestions:
                groups["minute"].append(task)
            continue
        if task.due_date:
            if task.due_date <= today:
                groups["now"].append(task)
            elif task.due_date <= today + WEEK:
                groups["week"].append(task)
            else:
                groups["later"].append(task)
        elif task.when == Task.WHEN_NO_RUSH:
            groups["later"].append(task)
        elif (
            task.kind == Task.KIND_AUTOMATIC
            and task.opened_at <= now - NOW_AFTER
        ):
            groups["now"].append(task)
        else:
            groups["week"].append(task)

    still_needed = list(
        _related(
            Task.objects.filter(
                created_by=user,
                status=Task.STATUS_OPEN,
                still_needed_asked_at__isnull=False,
            )
        )
    )
    groups["minute"] = still_needed + groups["minute"]

    grabs = [
        task
        for task in _related(
            Task.objects.filter(
                status=Task.STATUS_OPEN, user__isnull=True
            ).exclude(team_kind="")
        )
        if membership.can_act(task.team_kind, task.team_id, task.team_role)
    ]

    closed = list(
        _related(
            Task.objects.filter(
                user=user,
                status=Task.STATUS_DONE,
                closed_at__gte=now - WEEK,
            )
        ).order_by("-closed_at")
    )
    stopped = list(
        _related(
            Task.objects.filter(
                user=user,
                status=Task.STATUS_STOPPED,
                closed_at__gte=now - STOPPED_SHOWN_FOR,
            )
        ).order_by("-closed_at")
    )

    def rows(tasks):
        return serialize_tasks(tasks, user, membership)

    needs_you = sum(len(groups[name]) for name in ("now", "week", "later"))
    return {
        "me": people([user.pk]).get(user.pk),
        "paused": paused,
        "show_suggestions": show_suggestions,
        "can_assign": membership.leads_anything,
        "needs_you": 0 if paused else needs_you,
        "snoozed": snoozed,
        "now": rows(groups["now"]),
        "this_week": rows(groups["week"]),
        "later": rows(groups["later"]),
        "minute": rows(groups["minute"]),
        "up_for_grabs": rows(grabs),
        "closed_this_week": rows(closed),
        "stopped": rows(stopped),
    }


def needs_you_count(user) -> int:
    """The Neocom count: open tasks that need this pilot, not snoozed."""
    if is_paused(user):
        return 0
    now = timezone.now()
    return (
        Task.objects.filter(
            user=user, status=Task.STATUS_OPEN, weight=Weight.NEEDS_YOU
        )
        .filter(Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=now))
        .count()
    )


def task_detail(user, task: Task) -> dict:
    row = serialize_tasks([task], user)[0]
    comments = list(task.comments.all())
    who = people(note.author_id for note in comments)
    row["comments"] = [
        {
            "id": note.pk,
            "author": who.get(note.author_id),
            "body": note.body,
            "created_at": note.created_at,
        }
        for note in comments
    ]
    return row


# --- Team tab -----------------------------------------------------------


def _member_ids_by_corporation(corporation_ids: Iterable[int]) -> dict:

    result = defaultdict(set)
    for user_id, corporation_id in EvePlayer.objects.filter(
        primary_character__corporation_id__in=list(corporation_ids),
        user__isnull=False,
    ).values_list("user_id", "primary_character__corporation_id"):
        result[corporation_id].add(user_id)
    return result


def _member_ids_by_group(group_ids: Iterable[int]) -> dict:

    result = defaultdict(set)
    for user_id, group_id in TribeGroupMembership.objects.filter(
        tribe_group_id__in=list(group_ids), status="active"
    ).values_list("user_id", "tribe_group_id"):
        result[group_id].add(user_id)
    return result


def paused_ids(user_ids: set[int]) -> set[int]:

    paused = set(
        TaskPreferences.objects.filter(
            user_id__in=user_ids, paused=True
        ).values_list("user_id", flat=True)
    )
    paused |= set(
        UserCommunityStatus.objects.filter(
            user_id__in=user_ids,
            status__in=UserCommunityStatus.AWAY_STATUSES,
        ).values_list("user_id", flat=True)
    )
    return paused


def _counts(leader_q: Q, member_ids: set[int], since) -> tuple[int, int]:
    pilot_q = Q(user_id__in=member_ids, team_kind="", weight=Weight.NEEDS_YOU)
    scope = Task.objects.filter(leader_q | pilot_q)
    return (
        scope.filter(status=Task.STATUS_OPEN).count(),
        scope.filter(status=Task.STATUS_DONE, closed_at__gte=since).count(),
    )


def _corp_q(corporation_id: int) -> Q:
    return Q(team_kind=TeamKind.CORPORATION, team_id=corporation_id)


def _groups_q(group_ids: Iterable[int]) -> Q:
    return Q(team_kind=TeamKind.TRIBE_GROUP, team_id__in=list(group_ids))


def team_overview(user) -> dict:
    membership = Membership(user)
    since = timezone.now() - WEEK
    corps = membership.corporations
    by_corp = _member_ids_by_corporation(team.id for team in corps)
    tribes = membership.tribes
    by_group = _member_ids_by_group(
        gid for team in tribes for gid in team.group_ids
    )

    corporation_rows = []
    for team in corps:
        members = by_corp.get(team.id, set())
        members -= paused_ids(members)
        open_count, closed = _counts(_corp_q(team.id), members, since)
        corporation_rows.append(
            {
                "kind": "corporation",
                "id": team.id,
                "name": team.label,
                "open": open_count,
                "closed_this_week": closed,
                "detail": "",
            }
        )

    tribe_rows = []
    for team in tribes:
        members = set()
        for gid in team.group_ids:
            members |= by_group.get(gid, set())
        members -= paused_ids(members)
        open_count, closed = _counts(_groups_q(team.group_ids), members, since)
        count = len(team.group_ids)
        tribe_rows.append(
            {
                "kind": "tribe" if count > 1 else "tribe_group",
                "id": team.id,
                "name": team.label,
                "open": open_count,
                "closed_this_week": closed,
                "detail": f"{count} group{'s' if count != 1 else ''}",
            }
        )

    pilots = _rule_rollup(None, since) if user.is_superuser else []
    return {
        "corporations": corporation_rows,
        "tribes": tribe_rows,
        "pilots": pilots,
    }


def _rule_rollup(member_ids: Optional[set[int]], since) -> list[dict]:
    """Per pilot rule: how many wait and how many closed this week."""
    scope = Task.objects.filter(kind=Task.KIND_AUTOMATIC, team_kind="")
    if member_ids is not None:
        scope = scope.filter(user_id__in=member_ids)
    waiting = dict(
        scope.filter(status=Task.STATUS_OPEN)
        .order_by()
        .values("rule")
        .annotate(n=Count("id"))
        .values_list("rule", "n")
    )
    closed = dict(
        scope.filter(status=Task.STATUS_DONE, closed_at__gte=since)
        .order_by()
        .values("rule")
        .annotate(n=Count("id"))
        .values_list("rule", "n")
    )
    rows = []
    for rule in RULES.values():
        if not rule.is_pilot_rule:
            continue
        if not waiting.get(rule.code) and not closed.get(rule.code):
            continue
        rows.append(
            {
                "rule": rule.code,
                "label": rule.label,
                "weight": rule.weight,
                "waiting": waiting.get(rule.code, 0),
                "closed_this_week": closed.get(rule.code, 0),
            }
        )
    return rows


def _team_scope(user, kind: str, team_id: int):
    """(name, leader Q, member ids) for a team this user may view."""

    membership = Membership(user)
    if kind == "corporation":
        if not any(team.id == team_id for team in membership.corporations):
            return None
        name = EveCorporation.objects.filter(
            corporation_id=team_id
        ).values_list("name", flat=True).first() or str(team_id)
        members = _member_ids_by_corporation([team_id]).get(team_id, set())
        return name, _corp_q(team_id), members, []
    for team in membership.tribes:
        if team.id == team_id and (
            (kind == "tribe" and len(team.group_ids) > 1)
            or (kind == "tribe_group" and len(team.group_ids) == 1)
        ):
            by_group = _member_ids_by_group(team.group_ids)
            members = set().union(*by_group.values()) if by_group else set()
            groups = list(
                TribeGroup.objects.filter(pk__in=team.group_ids)
                .prefetch_related("chief_seats")
                .order_by("name")
            )
            name = (
                Tribe.objects.filter(pk=team_id)
                .values_list("name", flat=True)
                .first()
                if kind == "tribe"
                else team.label
            ) or team.label
            return name, _groups_q(team.group_ids), members, groups
    return None


def team_detail(user, kind: str, team_id: int) -> Optional[dict]:
    scope = _team_scope(user, kind, team_id)
    if scope is None:
        return None
    name, leader_q, members, groups = scope
    since = timezone.now() - WEEK
    paused = paused_ids(members)
    active = members - paused
    leader_tasks = list(
        _related(Task.objects.filter(leader_q, status=Task.STATUS_OPEN))
    )
    leader_closed = Task.objects.filter(
        leader_q, status=Task.STATUS_DONE, closed_at__gte=since
    ).count()
    group_rows = []
    if groups:
        by_group = _member_ids_by_group(group.pk for group in groups)
        seat_ids = {
            group.pk: [seat.user_id for seat in group_seats(group)]
            for group in groups
        }
        chiefs = people(uid for ids in seat_ids.values() for uid in ids)
        for group in groups:
            group_chiefs = [chiefs[uid] for uid in seat_ids[group.pk]]
            group_members = by_group.get(group.pk, set()) - paused
            open_count, closed = _counts(
                _groups_q([group.pk]), group_members, since
            )
            group_rows.append(
                {
                    "id": group.pk,
                    "tribe_id": group.tribe_id,
                    "name": group.name,
                    "chief": group_chiefs[0] if group_chiefs else None,
                    "chiefs": group_chiefs,
                    "open": open_count,
                    "closed_this_week": closed,
                }
            )
    return {
        "kind": kind,
        "id": team_id,
        "name": name,
        "leader_tasks": serialize_tasks(leader_tasks, user),
        "leader_closed_this_week": leader_closed,
        "groups": group_rows,
        "members": _rule_rollup(active, since),
        "members_paused": len(paused),
    }


def team_rule_pilots(user, kind: str, team_id: int, rule_code: str):
    """The pilots behind one needs-you rule. Suggestions stay counts."""
    rule = RULES.get(rule_code)
    if rule is None or rule.weight != Weight.NEEDS_YOU:
        return None
    scope = _team_scope(user, kind, team_id)
    if scope is None:
        return None
    members = scope[2]
    active = members - paused_ids(members)
    tasks = list(
        Task.objects.filter(
            kind=Task.KIND_AUTOMATIC,
            rule=rule_code,
            status=Task.STATUS_OPEN,
            user_id__in=active,
        ).order_by("opened_at")
    )
    who = people(task.user_id for task in tasks)
    now = timezone.now()
    return [
        {
            "task_id": task.pk,
            "pilot": who.get(task.user_id),
            "detail": task.title,
            "opened_at": task.opened_at,
            "reminded_at": task.reminded_at,
            "can_remind": can_remind(task, now)
            and wants_reminders(task.user_id),
            "reminders_off": not wants_reminders(task.user_id),
        }
        for task in tasks
    ]


# --- Projects -----------------------------------------------------------


def _project_counts(project_ids: list[int]) -> dict[int, dict]:
    rows = (
        Task.objects.filter(project_id__in=project_ids)
        .exclude(status=Task.STATUS_CANCELLED)
        .order_by()
        .values("project_id")
        .annotate(
            total=Count("id"),
            done=Count("id", filter=Q(status=Task.STATUS_DONE)),
            grabs=Count(
                "id",
                filter=Q(status=Task.STATUS_OPEN, user__isnull=True)
                & ~Q(team_kind=""),
            ),
        )
    )
    return {row["project_id"]: row for row in rows}


def _latest_updates(project_ids: list[int]) -> dict[int, ProjectUpdate]:
    latest = {}
    for update in ProjectUpdate.objects.filter(
        project_id__in=project_ids
    ).order_by("project_id", "-created_at"):
        latest.setdefault(update.project_id, update)
    return latest


def _project_row(project: Project, counts, latest, who, now) -> dict:
    update = latest.get(project.pk)
    row = counts.get(project.pk, {})
    started = project.created_at
    missing = (
        project.status == Project.STATUS_OPEN
        and started <= now - WEEK
        and (update is None or update.created_at <= now - WEEK)
    )
    return {
        "id": project.pk,
        "name": project.name,
        "kind": project.template.kind if project.template_id else "",
        "kind_label": project.template.name if project.template_id else "",
        "status": project.status,
        "lead": who.get(project.lead_id),
        "team_label": project.team_label,
        "link_url": project.link_url,
        "link_label": project.link_label,
        "starts_on": project.starts_on,
        "target_date": project.target_date,
        "finished_at": project.finished_at,
        "tasks_total": row.get("total", 0),
        "tasks_done": row.get("done", 0),
        "up_for_grabs": row.get("grabs", 0),
        "health": update.health if update else "",
        "update_missing": missing,
    }


def visible_projects(user):
    projects = Project.objects.select_related("template")
    if can_assign(user):
        return projects
    return projects.filter(
        Q(lead=user) | Q(tasks__user=user) | Q(tasks__created_by=user)
    ).distinct()


def projects_list(user) -> dict:
    now = timezone.now()
    projects = list(
        visible_projects(user).filter(
            Q(status=Project.STATUS_OPEN)
            | Q(finished_at__gte=now - timedelta(days=365))
        )
    )
    ids = [project.pk for project in projects]
    counts = _project_counts(ids)
    latest = _latest_updates(ids)
    who = people(project.lead_id for project in projects)
    led = set(Project.objects.filter(lead=user).values_list("pk", flat=True))
    involved = set(
        Task.objects.filter(project_id__in=ids, user=user).values_list(
            "project_id", flat=True
        )
    )
    rows = [_project_row(p, counts, latest, who, now) for p in projects]
    for row in rows:
        row["i_lead"] = row["id"] in led
        row["i_have_tasks"] = row["id"] in involved
    templates = [
        {
            "id": template.pk,
            "kind": template.kind,
            "name": template.name,
            "description": template.description,
            "task_count": template.task_count,
        }
        for template in ProjectTemplate.objects.filter(active=True).annotate(
            task_count=Count("tasks")
        )
    ]
    return {
        "can_start": can_assign(user),
        "open": [row for row in rows if row["status"] == Project.STATUS_OPEN],
        "finished": sorted(
            (row for row in rows if row["status"] != Project.STATUS_OPEN),
            key=lambda row: row["finished_at"] or now,
            reverse=True,
        ),
        "templates": templates,
    }


def project_detail(user, project: Project) -> dict:
    now = timezone.now()
    counts = _project_counts([project.pk])
    latest = _latest_updates([project.pk])
    tasks = list(_related(project.tasks.exclude(status=Task.STATUS_CANCELLED)))
    who = people(
        [project.lead_id]
        + [task.user_id for task in tasks]
        + [update.author_id for update in project.updates.all()]
    )
    row = _project_row(project, counts, latest, who, now)
    membership = Membership(user)
    serialized = {
        task["id"]: task for task in serialize_tasks(tasks, user, membership)
    }
    stages = []
    for stage in project.stages.all():
        stage_tasks = [
            serialized[t.pk] for t in tasks if t.stage_id == stage.pk
        ]
        stages.append(
            {
                "id": stage.pk,
                "name": stage.name,
                "done": sum(1 for t in stage_tasks if t["status"] == "done"),
                "total": len(stage_tasks),
                "tasks": stage_tasks,
            }
        )
    loose = [serialized[t.pk] for t in tasks if not t.stage_id]
    if loose:
        stages.append(
            {
                "id": 0,
                "name": "Other",
                "done": sum(1 for t in loose if t["status"] == "done"),
                "total": len(loose),
                "tasks": loose,
            }
        )
    open_tasks = [t for t in tasks if t.status == Task.STATUS_OPEN]
    waiting_longest = min(open_tasks, key=lambda t: t.opened_at, default=None)
    people_rows = defaultdict(lambda: {"open": 0, "done": 0})
    for task in tasks:
        if task.user_id:
            key = task.user_id
            if task.status == Task.STATUS_OPEN:
                people_rows[key]["open"] += 1
            elif task.status == Task.STATUS_DONE:
                people_rows[key]["done"] += 1
    if project.lead_id:
        people_rows[project.lead_id]  # pylint: disable=pointless-statement
    row.update(
        {
            "can_edit": can_edit_project(user, project),
            "stages": stages,
            "updates": [
                {
                    "id": update.pk,
                    "author": who.get(update.author_id),
                    "health": update.health,
                    "body": update.body,
                    "created_at": update.created_at,
                }
                for update in project.updates.all()
            ],
            "waiting_longest": (
                {
                    "id": waiting_longest.pk,
                    "title": waiting_longest.title,
                    "opened_at": waiting_longest.opened_at,
                }
                if waiting_longest
                else None
            ),
            "people": [
                {
                    "person": who.get(uid),
                    "is_lead": uid == project.lead_id,
                    "open": counts_["open"],
                    "done": counts_["done"],
                }
                for uid, counts_ in sorted(
                    people_rows.items(),
                    key=lambda item: (item[0] != project.lead_id, item[0]),
                )
                if who.get(uid)
            ],
        }
    )
    return row
