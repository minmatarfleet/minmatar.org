"""Task messages: the weekly list, a leader's reminder, a new task.

Sent by taskboard.messages, which holds them during a pilot's quiet hours.
All three are opt-in: Discord and Eve mail start off, and a pilot turns
them on in Tasks › Settings (or Account › Notifications).
"""

from __future__ import annotations

from app.links import site_url
from notifications.discord_buttons import link_button_components
from notifications.models import NotificationChannel
from notifications.registry import NotificationType, register

TASKS_WEEKLY_KEY = "tasks.weekly"
TASKS_REMINDER_KEY = "tasks.reminder"
TASKS_ASSIGNED_KEY = "tasks.assigned"

OPEN_LABEL = "Open my tasks"


def tasks_url() -> str:
    return site_url("/tasks/")


def _payload(title: str, body: str, message: str, url: str) -> dict:
    # The link button replaces Mark as read: opening the list is the action.
    return {
        "title": title,
        "body": body,
        "url": url,
        "discord_message": message,
        "discord_components": link_button_components(OPEN_LABEL, url),
        "subject": title,
        "eve_mail_body": message.replace("\n", "<br>"),
    }


def render_weekly(ctx: dict) -> dict:
    """ctx: name, lines (["Re-add Teysha Redblade · waiting 3 days", ...])."""
    lines = ctx.get("lines") or []
    count = len(lines)
    name = (ctx.get("name") or "").strip()
    things = "thing" if count == 1 else "things"
    greeting = f"You have {count} {things} waiting" + (
        f", {name}." if name else "."
    )
    listed = "\n".join(f"- {line}" for line in lines)
    url = ctx.get("url") or tasks_url()
    return _payload(
        title=greeting,
        body=greeting,
        message=f"{greeting}\n\n{listed}".strip(),
        url=url,
    )


def render_reminder(ctx: dict) -> dict:
    """ctx: leader, title."""
    leader = (ctx.get("leader") or "A leader").strip()
    title = (ctx.get("title") or "").strip()
    line = f"{leader} reminded you: **{title}**"
    return _payload(
        title=f"{leader} reminded you",
        body=title,
        message=line,
        url=ctx.get("url") or tasks_url(),
    )


def render_assigned(ctx: dict) -> dict:
    """ctx: author, title, when."""
    author = (ctx.get("author") or "A leader").strip()
    title = (ctx.get("title") or "").strip()
    when = (ctx.get("when") or "").strip()
    line = f"{author} gave you a task: **{title}**"
    if when:
        line += f" ({when})"
    return _payload(
        title=f"{author} gave you a task",
        body=title,
        message=line,
        url=ctx.get("url") or tasks_url(),
    )


TASKS_WEEKLY = register(
    NotificationType(
        key=TASKS_WEEKLY_KEY,
        feature="tasks",
        label="Weekly list",
        description=(
            "One message a week, only when something is waiting on you."
        ),
        channels=(NotificationChannel.DISCORD, NotificationChannel.EVE_MAIL),
        defaults={
            NotificationChannel.DISCORD: False,
            NotificationChannel.EVE_MAIL: False,
        },
        render=render_weekly,
        supports_topic_subscription=False,
    )
)

TASKS_REMINDER = register(
    NotificationType(
        key=TASKS_REMINDER_KEY,
        feature="tasks",
        label="A leader reminds me",
        description=(
            "At most once for each task, and only after it has waited "
            "two weeks."
        ),
        channels=(NotificationChannel.DISCORD, NotificationChannel.EVE_MAIL),
        defaults={
            NotificationChannel.DISCORD: False,
            NotificationChannel.EVE_MAIL: False,
        },
        render=render_reminder,
        supports_topic_subscription=False,
    )
)

TASKS_ASSIGNED = register(
    NotificationType(
        key=TASKS_ASSIGNED_KEY,
        feature="tasks",
        label="Someone gives me a task",
        description="Sent when a leader gives you a task.",
        channels=(NotificationChannel.DISCORD, NotificationChannel.EVE_MAIL),
        defaults={
            NotificationChannel.DISCORD: False,
            NotificationChannel.EVE_MAIL: False,
        },
        render=render_assigned,
        supports_topic_subscription=False,
    )
)
