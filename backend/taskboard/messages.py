"""Task messages on Discord (and Eve mail where a pilot chose it).

Three messages, all through the notifications app so a pilot can turn
each off on Account › Notifications:

- the weekly list (opt-in): one message on the set day and hour, only to
  pilots with something waiting, never to paused or On Leave pilots;
- a leader's reminder: once per task, only after it has waited
  (``remind_after_days``, default 14), only from that pilot's leaders;
- a new task: when a leader gives the pilot one.

Reminders and new-task messages that fall in a pilot's quiet hours wait
in TaskMessageHold and go out together when the quiet hours end.
Deliveries are paced by notify_users (stagger_rate_limited_channels); a
pilot with closed DMs shows up as a failed delivery and still has the
Neocom count.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from notifications.models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationPreference,
)
from notifications.service import notify_user, notify_users
from notifications.types.tasks import (
    TASKS_ASSIGNED_KEY,
    TASKS_REMINDER_KEY,
    TASKS_WEEKLY_KEY,
    tasks_url,
)
from taskboard.models import (
    Task,
    TaskDigestSettings,
    TaskMessageHold,
    TaskPreferences,
    Weight,
)
from taskboard.queries import paused_ids, people
from taskboard.reminders import can_remind
from taskboard.services import TaskError, is_paused

# A task joins the weekly list once it has waited this long (or is due
# within a week), so a fresh task doesn't ping on its first day.
WEEKLY_AFTER = timedelta(days=3)
WEEKLY_MAX_LINES = 10


# --- Quiet hours ---------------------------------------------------------


def in_quiet_hours(prefs: Optional[TaskPreferences], now: datetime) -> bool:
    if not prefs or prefs.quiet_start is None or prefs.quiet_end is None:
        return False
    start, end, hour = prefs.quiet_start, prefs.quiet_end, now.hour
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def send_task_message(
    user, type_key: str, context: dict, idempotency_key: str = ""
) -> bool:
    """Send now, or hold it until the pilot's quiet hours end.

    Returns True when it was sent now.
    """
    prefs = TaskPreferences.objects.filter(user=user).first()
    if in_quiet_hours(prefs, timezone.now()):
        TaskMessageHold.objects.create(
            user=user,
            type_key=type_key,
            context=context,
            idempotency_key=idempotency_key,
        )
        return False
    notify_user(
        user, type_key, context, idempotency_key=idempotency_key or None
    )
    return True


def flush_holds(now: Optional[datetime] = None) -> int:
    """Send held messages for pilots whose quiet hours have ended."""
    now = now or timezone.now()
    sent = 0
    holds = list(TaskMessageHold.objects.select_related("user"))
    prefs = {
        row.user_id: row
        for row in TaskPreferences.objects.filter(
            user_id__in={hold.user_id for hold in holds}
        )
    }
    for hold in holds:
        if in_quiet_hours(prefs.get(hold.user_id), now):
            continue
        notify_users(
            [hold.user],
            hold.type_key,
            hold.context,
            idempotency_key=hold.idempotency_key or None,
            stagger_rate_limited_channels=True,
        )
        hold.delete()
        sent += 1
    return sent


# --- A new task ----------------------------------------------------------


def task_assigned(task: Task, author) -> None:
    if not task.user_id or task.user_id == author.pk:
        return
    when = (
        f"due {task.due_date:%a %d %b}"
        if task.due_date
        else ("no rush" if task.when == Task.WHEN_NO_RUSH else "this week")
    )
    name = people([author.pk]).get(author.pk, {}).get("name", "")
    send_task_message(
        task.user,
        TASKS_ASSIGNED_KEY,
        {"author": name, "title": task.title, "when": when},
        idempotency_key=f"tasks.assigned:{task.pk}",
    )


# --- A leader's reminder -------------------------------------------------


def remind(leader, task: Task) -> Task:
    """One DM from a leader about one task. The caller checks the team."""
    now = timezone.now()
    if task.reminded_at:
        raise TaskError("They were already reminded about this.", 409)
    if not can_remind(task, now):
        raise TaskError("This one can't be reminded yet.")
    if is_paused(task.user):
        raise TaskError("They are away; their tasks are paused.")
    task.reminded_at = now
    task.reminded_by = leader
    task.save(update_fields=["reminded_at", "reminded_by"])
    name = people([leader.pk]).get(leader.pk, {}).get("name", "")
    send_task_message(
        task.user,
        TASKS_REMINDER_KEY,
        {"leader": name, "title": task.title},
        idempotency_key=f"tasks.reminder:{task.pk}",
    )
    return task


# --- The weekly list -----------------------------------------------------


def week_key(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{TASKS_WEEKLY_KEY}:{year}-W{week:02d}"


def opted_in_user_ids() -> set[int]:
    return set(
        NotificationPreference.objects.filter(
            notification_type=TASKS_WEEKLY_KEY, enabled=True
        ).values_list("user_id", flat=True)
    )


def weekly_lines(user_ids: set[int], now: datetime) -> dict[int, list[str]]:
    """Each pilot's waiting needs-you tasks, as one line each."""
    today = timezone.localdate(now)
    tasks = (
        Task.objects.filter(
            user_id__in=user_ids,
            status=Task.STATUS_OPEN,
            weight=Weight.NEEDS_YOU,
        )
        .filter(Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=now))
        .filter(
            Q(opened_at__lte=now - WEEKLY_AFTER)
            | Q(due_date__lte=today + timedelta(days=7))
        )
        .order_by("due_date", "opened_at")
    )
    lines: dict[int, list[str]] = {}
    for task in tasks:
        if task.due_date:
            when = f"due {task.due_date:%a %d %b}"
        else:
            days = (now - task.opened_at).days
            when = f"waiting {days} day{'s' if days != 1 else ''}"
        rows = lines.setdefault(task.user_id, [])
        if len(rows) < WEEKLY_MAX_LINES:
            rows.append(f"**{task.title}** · {when}")
    return lines


def is_send_time(settings: TaskDigestSettings, now: datetime) -> bool:
    return (
        settings.enabled
        and now.weekday() == settings.weekday
        and now.hour == settings.hour
    )


def send_weekly_lists(now: Optional[datetime] = None, force=False) -> dict:
    """Run hourly; sends once on the set day and hour (idempotent)."""
    now = now or timezone.now()
    settings = TaskDigestSettings.load()
    if not force and not is_send_time(settings, now):
        return {"sent": 0, "skipped": "not the send time"}
    user_ids = opted_in_user_ids()
    user_ids -= paused_ids(user_ids)
    lines = weekly_lines(user_ids, now)
    if not lines:
        return {"sent": 0}
    names = people(lines)
    users = list(User.objects.filter(pk__in=lines))
    notify_users(
        users,
        TASKS_WEEKLY_KEY,
        {"url": tasks_url()},
        idempotency_key=week_key(now),
        stagger_rate_limited_channels=True,
        user_contexts={
            uid: {
                "lines": rows,
                "name": names.get(uid, {}).get("name", "").split(" ")[0],
            }
            for uid, rows in lines.items()
        },
    )
    return {"sent": len(users)}


def last_send_time(settings: TaskDigestSettings, now: datetime) -> datetime:
    days_back = (now.weekday() - settings.weekday) % 7
    candidate = (now - timedelta(days=days_back)).replace(
        hour=settings.hour, minute=0, second=0, microsecond=0
    )
    if candidate > now:
        candidate -= timedelta(days=7)
    return candidate


def next_send_time(settings: TaskDigestSettings, now: datetime) -> datetime:
    return last_send_time(settings, now) + timedelta(days=7)


def weekly_stats(now: Optional[datetime] = None) -> dict:
    """What happened at the last send: who said yes, who got one."""
    now = now or timezone.now()
    settings = TaskDigestSettings.load()
    last = last_send_time(settings, now)
    deliveries = NotificationDelivery.objects.filter(
        notification_type=TASKS_WEEKLY_KEY,
        idempotency_key__startswith=week_key(last),
        channel=NotificationChannel.DISCORD,
    )
    return {
        "opted_in": len(opted_in_user_ids()),
        "had_waiting": deliveries.count(),
        "delivered": deliveries.filter(
            status__in=[
                NotificationDeliveryStatus.SENT,
                NotificationDeliveryStatus.READ,
            ]
        ).count(),
        "not_delivered": deliveries.filter(
            status__in=[
                NotificationDeliveryStatus.FAILED,
                NotificationDeliveryStatus.SKIPPED,
            ]
        ).count(),
        "last_sent_at": last,
        "next_send_at": next_send_time(settings, now),
    }


def set_weekly_dm(user, enabled: bool) -> None:
    """The pilot's yes or no to the weekly list (Discord)."""
    NotificationPreference.objects.update_or_create(
        user=user,
        notification_type=TASKS_WEEKLY_KEY,
        channel=NotificationChannel.DISCORD,
        defaults={"enabled": enabled},
    )
    TaskPreferences.objects.update_or_create(
        user=user, defaults={"weekly_prompt_answered": True}
    )


def weekly_dm_enabled(user) -> bool:
    return NotificationPreference.objects.filter(
        user=user,
        notification_type=TASKS_WEEKLY_KEY,
        channel=NotificationChannel.DISCORD,
        enabled=True,
    ).exists()


def show_weekly_prompt(user) -> bool:
    prefs = TaskPreferences.objects.filter(user=user).first()
    if prefs and prefs.weekly_prompt_answered:
        return False
    return not NotificationPreference.objects.filter(
        user=user, notification_type=TASKS_WEEKLY_KEY
    ).exists()
