"""Tribe notification type definitions and renderers."""

from __future__ import annotations

from notifications.models import NotificationChannel
from notifications.registry import NotificationType, register

TRIBE_MEMBERSHIP_REQUESTED_KEY = "tribes.membership_requested"


def render_membership_requested(ctx: dict) -> dict:
    group_name = ctx["group_name"]
    tribe_name = ctx["tribe_name"]
    applicant = ctx["applicant"]
    title = "New tribe membership application"
    # Same wording as the plain DM chiefs got before this was a
    # notification type.
    discord_message = (
        f"**{title}** for **{group_name}** ({tribe_name}): "
        f"{applicant} has applied. Please review in the admin panel."
    )
    return {
        "title": title,
        "body": f"{applicant} applied to {group_name} ({tribe_name}).",
        "url": ctx.get("url") or "",
        "discord_message": discord_message,
    }


TRIBE_MEMBERSHIP_REQUESTED = register(
    NotificationType(
        key=TRIBE_MEMBERSHIP_REQUESTED_KEY,
        feature="tribes",
        label="Applications to a group I lead",
        description=(
            "Ping me when a pilot applies to a tribe group I am chief of."
        ),
        channels=(
            NotificationChannel.DISCORD,
            NotificationChannel.WEB,
        ),
        # Discord on, as before; web push is opt-in.
        defaults={
            NotificationChannel.DISCORD: True,
            NotificationChannel.WEB: False,
        },
        render=render_membership_requested,
        supports_topic_subscription=False,
    )
)
