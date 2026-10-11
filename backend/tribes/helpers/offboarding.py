"""Offboard tribe memberships when affiliation no longer grants tribes.apply."""

import logging

from django.utils import timezone

from groups.helpers.feature_access import can_use_feature
from tribes.models import TribeGroupMembership

logger = logging.getLogger(__name__)

_OPEN_STATUSES = (
    TribeGroupMembership.STATUS_ACTIVE,
    TribeGroupMembership.STATUS_PENDING,
)


def inactivate_tribe_membership(
    membership: TribeGroupMembership,
    *,
    reason: str = "removed",
) -> None:
    membership.status = TribeGroupMembership.STATUS_INACTIVE
    membership.left_at = timezone.now()
    membership.history_inactive_reason = reason
    membership.save(update_fields=["status", "left_at"])


def offboard_tribe_memberships_without_feature(user) -> int:
    """Inactivate pending/active memberships the user can no longer apply to."""
    open_memberships = (
        TribeGroupMembership.objects.filter(
            user=user,
            status__in=_OPEN_STATUSES,
        )
        .select_related("tribe_group__tribe")
        .prefetch_related("tribe_group__allowed_affiliations")
    )
    count = 0
    for membership in open_memberships:
        if can_use_feature(
            user, "tribes.apply", tribe_group=membership.tribe_group
        ):
            continue
        logger.info(
            "User %s lost tribes.apply for %s; inactivating membership",
            user,
            membership.tribe_group,
        )
        inactivate_tribe_membership(membership)
        count += 1
    return count
