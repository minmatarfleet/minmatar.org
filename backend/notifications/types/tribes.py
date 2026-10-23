"""Tribe notification type definitions and renderers."""

from __future__ import annotations

from notifications.discord_format import feature_color
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


TRIBE_INVITED_KEY = "tribes.invited"
TRIBE_INVITE_ANSWERED_KEY = "tribes.invite_answered"


def render_invited(ctx: dict) -> dict:
    """The invite DM: who asked, the group, the note, and two buttons.

    Open invite links to the group page (the pilot picks characters there);
    Decline is a bot button. ``discord_components`` replaces the usual
    Mark as read button.
    """
    # pylint: disable-next=import-outside-toplevel
    from tribes.helpers.invitation_discord import invite_components

    group_name = ctx["group_name"]
    tribe_name = ctx["tribe_name"]
    inviter = ctx["inviter"]
    note = (ctx.get("note") or "").strip()
    url = ctx.get("url") or ""
    title = f"You’re invited to {group_name}"
    body = (
        f"{inviter} invited you to join {group_name} in the {tribe_name} "
        "tribe. No application needed: open the invite, pick your "
        "characters and you’re in."
    )
    description = (
        f"**{inviter}** invited you to join **{group_name}** in the "
        f"{tribe_name} tribe. No application needed: open the invite, pick "
        "your characters and you’re in."
    )
    if note:
        description += f"\n> {note}"
    fields = []
    if ctx.get("requirements"):
        fields.append(
            {"name": "Group needs", "value": ctx["requirements"][:1024]}
        )
    if ctx.get("expires"):
        fields.append({"name": "Expires", "value": ctx["expires"]})
    embed = {
        "author": {"name": "Tribes"},
        "color": feature_color("tribes"),
        "title": title,
        "description": description,
    }
    if url:
        embed["url"] = url
    if fields:
        embed["fields"] = fields
    return {
        "title": title,
        "body": body,
        "url": url,
        "discord_message": description,
        "discord_embed": embed,
        "discord_components": invite_components(ctx["invitation_id"], url),
    }


def render_invite_answered(ctx: dict) -> dict:
    group_name = ctx["group_name"]
    pilot = ctx["pilot"]
    if ctx.get("outcome") == "accepted":
        title = f"{pilot} joined {group_name}"
        body = (
            f"{pilot} accepted your invite. They have the {group_name} "
            "Discord role now."
        )
    else:
        title = f"{pilot} declined your invite to {group_name}"
        reinvite = ctx.get("reinvite_after")
        body = (
            f"You can invite {pilot} again from {reinvite}."
            if reinvite
            else f"{pilot} said no for now."
        )
    return {
        "title": title,
        "body": body,
        "url": ctx.get("url") or "",
        "discord_message": f"**{title}**\n{body}",
    }


TRIBE_INVITED = register(
    NotificationType(
        key=TRIBE_INVITED_KEY,
        feature="tribes",
        label="Invitations to a tribe group",
        description=(
            "Ping me when a chief invites me to their tribe group. Invites "
            "still show on the group page when this is off."
        ),
        channels=(
            NotificationChannel.DISCORD,
            NotificationChannel.WEB,
        ),
        defaults={
            NotificationChannel.DISCORD: True,
            NotificationChannel.WEB: True,
        },
        render=render_invited,
        supports_topic_subscription=False,
    )
)


TRIBE_INVITE_ANSWERED = register(
    NotificationType(
        key=TRIBE_INVITE_ANSWERED_KEY,
        feature="tribes",
        label="Answers to my tribe invitations",
        description=(
            "Ping me when a pilot I invited joins my group or declines."
        ),
        channels=(
            NotificationChannel.DISCORD,
            NotificationChannel.WEB,
        ),
        defaults={
            NotificationChannel.DISCORD: True,
            NotificationChannel.WEB: False,
        },
        render=render_invite_answered,
        supports_topic_subscription=False,
    )
)
