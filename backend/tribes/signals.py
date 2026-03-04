import logging

from django.db.models import signals
from django.dispatch import receiver

from tribes.models import (
    TribeGroupMembership,
    TribeGroupMembershipHistory,
)

logger = logging.getLogger(__name__)


@receiver(
    signals.pre_save,
    sender=TribeGroupMembership,
    dispatch_uid="tribe_group_membership_pre_save",
)
def tribe_group_membership_pre_save(sender, instance, **kwargs):
    """
    Cache the previous status before save so post_save can detect changes
    and write a TribeGroupMembershipHistory row.
    """
    if instance.pk:
        try:
            instance.history_pre_save_status = (
                TribeGroupMembership.objects.get(pk=instance.pk).status
            )
        except TribeGroupMembership.DoesNotExist:
            instance.history_pre_save_status = None
    else:
        instance.history_pre_save_status = None


@receiver(
    signals.post_save,
    sender=TribeGroupMembership,
    dispatch_uid="tribe_group_membership_post_save",
)
def tribe_group_membership_post_save(sender, instance, created, **kwargs):
    """
    1. Write a TribeGroupMembershipHistory row whenever status changes.
    2. Sync auth.Group membership:
       - active  → add user to tribe_group.group AND parent tribe.group
       - inactive → remove user from tribe_group.group;
                    remove from tribe.group only if no other active memberships remain
    """
    tribe_group = instance.tribe_group
    tribe = tribe_group.tribe
    user = instance.user

    # ── History row ────────────────────────────────────────────────────────
    previous_status = instance.history_pre_save_status
    current_status = instance.status

    if created or (
        previous_status is not None and previous_status != current_status
    ):
        from_status = previous_status or ""
        reason = ""
        if current_status == TribeGroupMembership.STATUS_INACTIVE:
            reason = instance.history_inactive_reason or ""
        elif current_status == TribeGroupMembership.STATUS_ACTIVE:
            reason = "approved"

        TribeGroupMembershipHistory.objects.create(
            membership=instance,
            from_status=from_status,
            to_status=current_status,
            changed_by=instance.history_changed_by,
            reason=reason,
        )

    # ── Auth group sync ────────────────────────────────────────────────────
    if instance.status == TribeGroupMembership.STATUS_ACTIVE:
        if tribe_group.group:
            user.groups.add(tribe_group.group)
            logger.info(
                "Added user %s to auth group %s (tribe group approved)",
                user,
                tribe_group.group,
            )
        if tribe.group:
            user.groups.add(tribe.group)
            logger.info(
                "Added user %s to auth group %s (tribe approved)",
                user,
                tribe.group,
            )

    elif instance.status == TribeGroupMembership.STATUS_INACTIVE:
        if tribe_group.group:
            user.groups.remove(tribe_group.group)
            logger.info(
                "Removed user %s from auth group %s (tribe group left/removed)",
                user,
                tribe_group.group,
            )

        # Remove from the tribe-level group only if the user has no other
        # active memberships in any TribeGroup belonging to this tribe.
        has_other_active = (
            TribeGroupMembership.objects.filter(
                user=user,
                status=TribeGroupMembership.STATUS_ACTIVE,
                tribe_group__tribe=tribe,
            )
            .exclude(pk=instance.pk)
            .exists()
        )

        if not has_other_active and tribe.group:
            user.groups.remove(tribe.group)
            logger.info(
                "Removed user %s from tribe auth group %s (no remaining active memberships)",
                user,
                tribe.group,
            )
