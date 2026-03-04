"""
Celery tasks for the tribes app.

Tasks:
- create_tribe_membership_reminders: Discord reminders for pending memberships.
- remove_tribe_members_without_permission: Removes members lacking base permission.
"""

import logging
from collections import defaultdict

from django.utils import timezone

from app.celery import app
from discord.client import DiscordClient

from tribes.models import TribeGroupMembership

discord = DiscordClient()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Discord reminder task
# ---------------------------------------------------------------------------


def _discord_mention(user) -> str | None:
    """Return a Discord mention string for a user, or None if unavailable."""
    try:
        return f"<@{user.discord_user.id}>"
    except Exception:  # pylint: disable=broad-except
        return None


def _build_reminder_message(tribe_group, memberships: list) -> str:
    """Build the Discord reminder message for a tribe group's pending applications."""
    lines = ["**Pending Tribe Membership Applications**"]
    for m in memberships:
        mention = _discord_mention(m.user)
        if mention:
            lines.append(f"- {mention} → {tribe_group.name}")
        else:
            lines.append(f"- {m.user.username} → {tribe_group.name}")
    lines.append("\nPlease review applications in the admin panel.")

    mentions = []
    if tribe_group.chief:
        chief_mention = _discord_mention(tribe_group.chief)
        if chief_mention:
            mentions.append(chief_mention)
    for elder in tribe_group.elders.all():
        elder_mention = _discord_mention(elder)
        if elder_mention:
            mentions.append(elder_mention)
    if mentions:
        lines.append(" ".join(mentions))

    return "\n".join(lines)


def _send_group_reminder(tribe_group, memberships: list) -> None:
    """Send a pending-application reminder for one tribe group."""
    channel_id = (
        tribe_group.discord_channel_id or tribe_group.tribe.discord_channel_id
    )
    if not channel_id:
        logger.info(
            "TribeGroup %s has no Discord channel configured", tribe_group
        )
        return
    message = _build_reminder_message(tribe_group, memberships)
    try:
        discord.create_message(channel_id, message)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Failed to send reminder to Discord channel %s: %s",
            channel_id,
            exc,
        )


@app.task()
def create_tribe_membership_reminders():
    """
    Post Discord reminders to tribe/group channels for any pending
    TribeGroupMembership applications so chiefs and elders can action them.
    """
    pending = (
        TribeGroupMembership.objects.filter(
            status=TribeGroupMembership.STATUS_PENDING
        )
        .select_related("tribe_group__tribe", "tribe_group", "user")
        .prefetch_related("tribe_group__elders")
    )

    by_group: dict = defaultdict(list)
    for membership in pending:
        by_group[membership.tribe_group].append(membership)

    for tribe_group, memberships in by_group.items():
        _send_group_reminder(tribe_group, memberships)


# ---------------------------------------------------------------------------
# Permission cleanup task
# ---------------------------------------------------------------------------


@app.task()
def remove_tribe_members_without_permission():
    """
    Remove users from all TribeGroups if they no longer have the base
    'tribes.add_tribegroupmembership' permission (e.g. they left the alliance).

    Sets status to 'inactive' and records left_at, which triggers the
    post_save signal to remove the user from the auth.Group.
    """
    active_memberships = TribeGroupMembership.objects.filter(
        status=TribeGroupMembership.STATUS_ACTIVE
    ).select_related("user", "tribe_group__tribe")

    for membership in active_memberships:
        user = membership.user
        try:
            if not user.has_perm("tribes.add_tribegroupmembership"):
                logger.info(
                    "User %s lacks tribes permission; removing from %s",
                    user,
                    membership.tribe_group,
                )
                membership.status = TribeGroupMembership.STATUS_INACTIVE
                membership.left_at = timezone.now()
                membership.history_inactive_reason = "removed"
                membership.save(update_fields=["status", "left_at"])
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Error checking permission for user %s in group %s: %s",
                user,
                membership.tribe_group,
                exc,
            )
