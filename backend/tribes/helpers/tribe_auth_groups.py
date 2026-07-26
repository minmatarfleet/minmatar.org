"""Keep auth.Group membership aligned with TribeGroupMembership (inactive → remove groups)."""

import logging

from tribes.models import TribeGroupMembership, TribeGroupRank

logger = logging.getLogger(__name__)


def _rank_auth_group_ids_for_tribe_group(tribe_group_id: int) -> set[int]:
    return set(
        TribeGroupRank.objects.filter(
            tribe_group_id=tribe_group_id,
            group_id__isnull=False,
        ).values_list("group_id", flat=True)
    )


def sync_membership_rank_auth_groups(membership: TribeGroupMembership) -> None:
    """
    Align the user's auth groups with membership.rank for an active membership.

    Removes other rank-linked groups in the same tribe group, then adds the
    current rank's group when configured.
    """
    if membership.status != TribeGroupMembership.STATUS_ACTIVE:
        return

    user = membership.user
    tribe_group = membership.tribe_group
    rank_auth_ids = _rank_auth_group_ids_for_tribe_group(tribe_group.pk)
    if not rank_auth_ids:
        return

    keep_group_id = None
    if membership.rank_id is not None and membership.rank.group_id is not None:
        keep_group_id = membership.rank.group_id

    for group_id in rank_auth_ids:
        if group_id == keep_group_id:
            continue
        if user.groups.filter(pk=group_id).exists():
            user.groups.remove(group_id)
            logger.info(
                "Removed user %s from rank auth group id=%s (tribe group %s)",
                user,
                group_id,
                tribe_group,
            )

    if keep_group_id and not user.groups.filter(pk=keep_group_id).exists():
        user.groups.add(keep_group_id)
        logger.info(
            "Added user %s to rank auth group id=%s (%s)",
            user,
            keep_group_id,
            membership.rank,
        )


def remove_rank_auth_groups_for_membership(
    membership: TribeGroupMembership,
) -> None:
    """Remove all rank-linked auth groups for this membership's tribe group."""
    user = membership.user
    for group_id in _rank_auth_group_ids_for_tribe_group(
        membership.tribe_group_id
    ):
        if user.groups.filter(pk=group_id).exists():
            user.groups.remove(group_id)
            logger.info(
                "Removed user %s from rank auth group id=%s (membership inactive)",
                user,
                group_id,
            )


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

    remove_rank_auth_groups_for_membership(membership)

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
