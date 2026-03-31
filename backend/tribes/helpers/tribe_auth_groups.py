"""Keep auth.Group membership aligned with TribeGroupMembership (inactive → remove groups)."""

import logging

from tribes.models import TribeGroupMembership

logger = logging.getLogger(__name__)


def remove_tribe_auth_groups_for_inactive_membership(
    membership: TribeGroupMembership,
) -> None:
    """
    Remove the user from tribe_group.group and, when appropriate, tribe.group.

    Matches the inactive branch of tribe_group_membership_post_save: idempotent
    (only removes when the user is still in the group) so periodic cleanup
    does not spam logs.
    """
    if membership.status != TribeGroupMembership.STATUS_INACTIVE:
        return

    tribe_group = membership.tribe_group
    tribe = tribe_group.tribe
    user = membership.user

    tg_auth = tribe_group.group
    if tg_auth and user.groups.filter(pk=tg_auth.pk).exists():
        user.groups.remove(tg_auth)
        logger.info(
            "Removed user %s from auth group %s (tribe group inactive)",
            user,
            tg_auth,
        )

    has_other_active = (
        TribeGroupMembership.objects.filter(
            user=user,
            status=TribeGroupMembership.STATUS_ACTIVE,
            tribe_group__tribe=tribe,
        )
        .exclude(pk=membership.pk)
        .exists()
    )

    if not has_other_active:
        tribe_auth = tribe.group
        if tribe_auth and user.groups.filter(pk=tribe_auth.pk).exists():
            user.groups.remove(tribe_auth)
            logger.info(
                "Removed user %s from tribe auth group %s (inactive, no other active memberships)",
                user,
                tribe_auth,
            )
