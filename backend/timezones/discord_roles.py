"""Keep the bracket Discord roles in step with PilotTimezone.

Each bracket is an auth group; discord.signals mirrors group membership to
the Discord role and aborts the change when Discord fails
(docs/auth/discord-groups.md). This module is the desired-state reconciler
for that source: eligible pilots hold their brackets' groups, nobody else
holds any. A failed add or remove is retried on the next run.

Off unless settings.TIMEZONES_DISCORD_ROLES is set, so assessments can be
reviewed in admin before any role moves.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Iterable

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.dispatch import receiver

from discord.exceptions import DiscordRoleAssignmentError
from timezones.brackets import BRACKET_CODES
from timezones.models import PilotTimezone, TimezoneRole
from timezones.services import pilot_timezone_changed

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(settings.TIMEZONES_DISCORD_ROLES)


def ensure_groups() -> dict[str, Group]:
    """Bracket code -> auth group, creating any that are missing.

    Creating a group creates (or adopts, by name) its Discord role.
    """
    roles = {
        role.code: role.group
        for role in TimezoneRole.objects.select_related("group")
    }
    for code in BRACKET_CODES:
        if code in roles:
            continue
        group, _ = Group.objects.get_or_create(name=code)
        TimezoneRole.objects.create(code=code, group=group)
        roles[code] = group
        logger.info("Created timezone role group %s", code)
    return roles


def desired_brackets(user_ids: Iterable[int] | None = None) -> dict[int, set]:
    rows = PilotTimezone.objects.filter(eligible=True)
    if user_ids is not None:
        rows = rows.filter(user_id__in=list(user_ids))
    return {
        user_id: set(brackets or [])
        for user_id, brackets in rows.values_list("user_id", "brackets")
    }


def apply_roles(user_ids: Iterable[int] | None = None) -> Counter:
    """Add and remove bracket groups so membership matches PilotTimezone.

    With ``user_ids`` None, reconciles everyone: eligible pilots and anyone
    holding a bracket group.
    """
    outcome: Counter = Counter()
    if not enabled():
        return outcome
    groups = ensure_groups()
    group_codes = {group.id: code for code, group in groups.items()}
    if user_ids is not None:
        user_ids = {int(uid) for uid in user_ids}
    desired = desired_brackets(user_ids)

    held: dict[int, set] = {}
    memberships = User.groups.through.objects.filter(
        group_id__in=list(group_codes)
    )
    if user_ids is not None:
        memberships = memberships.filter(user_id__in=user_ids)
    for user_id, group_id in memberships.values_list("user_id", "group_id"):
        held.setdefault(user_id, set()).add(group_codes[group_id])

    targets = set(desired) | set(held)
    users = User.objects.in_bulk(list(targets))
    for user_id in sorted(targets):
        user = users.get(user_id)
        if user is None:
            continue
        want = desired.get(user_id, set())
        have = held.get(user_id, set())
        for code in sorted(want - have):
            outcome[_change(user, groups[code], add=True)] += 1
        for code in sorted(have - want):
            outcome[_change(user, groups[code], add=False)] += 1
    return outcome


def _change(user: User, group: Group, add: bool) -> str:
    try:
        # A savepoint, so a refused change leaves the caller's transaction
        # usable.
        with transaction.atomic():
            if add:
                user.groups.add(group)
            else:
                user.groups.remove(group)
    except DiscordRoleAssignmentError as e:
        # The next run retries; Django membership is unchanged.
        logger.warning(
            "Could not %s timezone role %s for user %s: %s",
            "add" if add else "remove",
            group.name,
            user.id,
            e,
        )
        return "failed"
    logger.info(
        "%s timezone role %s for user %s",
        "Added" if add else "Removed",
        group.name,
        user.id,
    )
    return "added" if add else "removed"


@receiver(pilot_timezone_changed, dispatch_uid="timezones_apply_discord_roles")
def apply_on_change(
    sender, instance, **kwargs
):  # pylint: disable=unused-argument
    apply_roles([instance.user_id])
