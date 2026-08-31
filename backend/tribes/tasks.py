"""
Celery tasks for the tribes app.

Tasks:
- create_tribe_membership_reminders: Discord reminders for pending memberships.
- remove_tribe_members_without_permission: Removes members lacking base permission.
- ensure_tribe_chiefs_have_group_memberships: Active membership for each tribe chief.
"""

import logging
from collections import defaultdict

from app.celery import app
from django.contrib.auth.models import User
from discord.client import DiscordClient

from tribes.helpers.chief_membership import (
    ensure_tribe_chiefs_have_group_memberships as _ensure_chief_memberships,
)
from tribes.helpers.offboarding import (
    offboard_tribe_memberships_without_feature,
)
from tribes.helpers.tribe_auth_groups import (
    remove_tribe_auth_groups_for_inactive_membership,
)
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
    TribeGroupMembership applications so chiefs can action them.
    """
    pending = TribeGroupMembership.objects.filter(
        status=TribeGroupMembership.STATUS_PENDING
    ).select_related("tribe_group__tribe", "tribe_group", "user")

    by_group: dict = defaultdict(list)
    for membership in pending:
        by_group[membership.tribe_group].append(membership)

    for tribe_group, memberships in by_group.items():
        _send_group_reminder(tribe_group, memberships)


# ---------------------------------------------------------------------------
# Permission cleanup task
# ---------------------------------------------------------------------------


@app.task()
def ensure_tribe_chiefs_have_group_memberships():
    """Hourly: ensure each tribe chief has active membership in all tribe groups."""
    _ensure_chief_memberships()


@app.task()
def remove_tribe_members_without_permission():
    """
    Remove users from TribeGroups they no longer qualify to apply to
    (e.g. affiliation change or left the alliance).

    Also fixes stale auth.Group links for inactive memberships.
    """
    user_ids = (
        TribeGroupMembership.objects.filter(
            status__in=(
                TribeGroupMembership.STATUS_ACTIVE,
                TribeGroupMembership.STATUS_PENDING,
            )
        )
        .values_list("user_id", flat=True)
        .distinct()
    )

    for user_id in user_ids:
        try:
            user = User.objects.get(pk=user_id)
            offboard_tribe_memberships_without_feature(user)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Error offboarding tribe memberships for user %s: %s",
                user_id,
                exc,
            )

    inactive_memberships = TribeGroupMembership.objects.filter(
        status=TribeGroupMembership.STATUS_INACTIVE
    ).select_related(
        "user",
        "tribe_group__tribe",
        "tribe_group__group",
        "tribe_group__tribe__group",
    )

    for membership in inactive_memberships:
        try:
            remove_tribe_auth_groups_for_inactive_membership(membership)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Error syncing auth groups for inactive membership %s: %s",
                membership.pk,
                exc,
            )
