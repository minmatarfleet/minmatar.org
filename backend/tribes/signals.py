import logging

from django.contrib.auth.models import User
from django.db.models import signals
from django.dispatch import receiver

from tribes.helpers.external_guild import (
    on_membership_became_active,
    on_membership_became_inactive,
    prepare_seats_for_user_delete,
)
from tribes.helpers.tribe_auth_groups import (
    remove_tribe_auth_groups_for_inactive_membership,
    sync_membership_rank_auth_groups,
)
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
    Cache the previous status and rank before save so post_save can detect
    changes and write a TribeGroupMembershipHistory row.
    """
    if instance.pk:
        try:
            previous = TribeGroupMembership.objects.get(pk=instance.pk)
            instance.history_pre_save_status = previous.status
            instance.history_pre_save_rank_id = previous.rank_id
        except TribeGroupMembership.DoesNotExist:
            instance.history_pre_save_status = None
            instance.history_pre_save_rank_id = None
    else:
        instance.history_pre_save_status = None
        instance.history_pre_save_rank_id = None


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
    3. Sync rank auth groups when active; strip rank groups when inactive.
    4. Sync isolated external Discord guild seats (never fail-closed).
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
        sync_membership_rank_auth_groups(instance)

    elif instance.status == TribeGroupMembership.STATUS_INACTIVE:
        remove_tribe_auth_groups_for_inactive_membership(instance)

    # External guild: isolated; never fail the membership save.
    status_changed = created or (
        previous_status is not None and previous_status != current_status
    )
    if status_changed:
        try:
            if current_status == TribeGroupMembership.STATUS_ACTIVE:
                on_membership_became_active(instance)
            elif current_status == TribeGroupMembership.STATUS_INACTIVE:
                on_membership_became_inactive(instance)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "External guild sync failed for membership %s",
                instance.pk,
            )


@receiver(
    signals.pre_delete,
    sender=User,
    dispatch_uid="tribe_external_guild_user_pre_delete",
)
def tribe_external_guild_user_pre_delete(sender, instance, **kwargs):
    """Snapshot usernames and kick external guild seats before User CASCADE."""
    try:
        prepare_seats_for_user_delete(instance)
    except Exception:  # pylint: disable=broad-except
        logger.exception(
            "External guild pre-delete cleanup failed for user %s",
            instance.pk,
        )
