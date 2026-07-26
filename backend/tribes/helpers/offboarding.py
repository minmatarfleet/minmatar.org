"""Offboard tribe memberships when affiliation no longer grants tribes.apply."""

import logging

from django.utils import timezone

from groups.helpers.feature_access import can_use_feature
from tribes.models import TribeGroupMembership

logger = logging.getLogger(__name__)


def offboard_tribe_memberships_without_feature(user) -> int:
    """
    Inactivate active tribe memberships when the user cannot apply to tribes.
    Returns the number of memberships inactivated.
    """
    if can_use_feature(user, "tribes.apply"):
        return 0

    active_memberships = TribeGroupMembership.objects.filter(
        user=user,
        status=TribeGroupMembership.STATUS_ACTIVE,
    )
    count = 0
    for membership in active_memberships:
        logger.info(
            "User %s lost tribes.apply; inactivating membership in %s",
            user,
            membership.tribe_group,
        )
        membership.status = TribeGroupMembership.STATUS_INACTIVE
        membership.left_at = timezone.now()
        membership.history_inactive_reason = "removed"
        membership.save(update_fields=["status", "left_at"])
        count += 1
    return count
