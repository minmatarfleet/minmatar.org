"""A superuser asks a pilot to re-add characters (Manage › ESI health).

The site never sends this by itself: a superuser picks the pilots and
presses Send, at most once a week per pilot (esi_health.services). Discord
starts on so it reaches pilots who never turned on task messages; a pilot
can still turn it off in Account › Notifications.
"""

from __future__ import annotations

from notifications.models import NotificationChannel
from notifications.registry import NotificationType, register
from notifications.types.tasks import _payload, tasks_url

ESI_MESSAGE_KEY = "tasks.esi_message"


def render_esi_message(ctx: dict) -> dict:
    """ctx: sender, first (a character name), others (how many more)."""
    sender = (ctx.get("sender") or "Alliance leadership").strip()
    first = (ctx.get("first") or "your characters").strip()
    others = int(ctx.get("others") or 0)
    if others == 1:
        who = f"**{first}** and 1 other character"
    elif others:
        who = f"**{first}** and {others} other characters"
    else:
        who = f"**{first}**"
    title = f"{sender}, for the alliance: please re-add your characters"
    body = (
        f"We can't read {who} from EVE any more. Fleet sign-ups and SRP "
        "need them. It takes a minute per character."
    )
    return _payload(
        title=title,
        body=body.replace("**", ""),
        message=f"**{title}**\n{body}",
        url=ctx.get("url") or tasks_url(),
    )


ESI_MESSAGE = register(
    NotificationType(
        key=ESI_MESSAGE_KEY,
        feature="tasks",
        label="A superuser asks me to re-add characters",
        description=(
            "Sent by hand from Manage › ESI health, at most once a week."
        ),
        channels=(NotificationChannel.DISCORD,),
        defaults={NotificationChannel.DISCORD: True},
        render=render_esi_message,
        supports_topic_subscription=False,
    )
)
