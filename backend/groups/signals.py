import logging

from django.db.models import signals
from django.dispatch import receiver

from groups.helpers import sync_user_community_groups
from groups.models import (
    UserAffiliation,
    UserCommunityStatus,
    UserCommunityStatusHistory,
)

logger = logging.getLogger(__name__)

# Transient cache for previous status between pre_save and post_save (avoids protected attr).
_previous_status_cache = {}


@receiver(
    signals.pre_delete,
    sender=UserAffiliation,
    dispatch_uid="user_affiliation_pre_delete",
)
def user_affiliation_pre_delete(sender, instance, **kwargs):
    logger.info("User affiliation deleted, syncing user community groups")
    sync_user_community_groups(instance.user)


@receiver(
    signals.post_save,
    sender=UserAffiliation,
    dispatch_uid="user_affiliation_post_save",
)
def user_affiliation_post_save(sender, instance, created, **kwargs):
    if instance.affiliation.requires_trial:
        UserCommunityStatus.objects.get_or_create(
            user=instance.user,
            defaults={"status": UserCommunityStatus.STATUS_TRIAL},
        )
    else:
        # Current affiliation does not require trial; clear trial if they have it
        # (e.g. they were Alliance and are now Guest/Militia).
        try:
            ucs = UserCommunityStatus.objects.get(user=instance.user)
            if ucs.status == UserCommunityStatus.STATUS_TRIAL:
                ucs.status = UserCommunityStatus.STATUS_ACTIVE
                ucs.save(update_fields=["status"])
        except UserCommunityStatus.DoesNotExist:
            pass
    logger.info("User affiliation saved, syncing user community groups")
    instance.user.refresh_from_db()
    sync_user_community_groups(instance.user)


@receiver(
    signals.pre_save,
    sender=UserCommunityStatus,
    dispatch_uid="user_community_status_pre_save",
)
def user_community_status_pre_save(sender, instance, **kwargs):
    key = id(instance)
    if instance.pk:
        try:
            old = UserCommunityStatus.objects.get(pk=instance.pk)
            _previous_status_cache[key] = old.status
        except UserCommunityStatus.DoesNotExist:
            _previous_status_cache[key] = None
    else:
        _previous_status_cache[key] = None


@receiver(
    signals.post_save,
    sender=UserCommunityStatus,
    dispatch_uid="user_community_status_post_save",
)
def user_community_status_post_save(sender, instance, created, **kwargs):
    previous = _previous_status_cache.pop(id(instance), None)
    if created or previous != instance.status:
        UserCommunityStatusHistory.objects.create(
            user=instance.user,
            from_status=previous,
            to_status=instance.status,
            reason="",
            changed_by=None,
        )
    logger.info("User community status saved, syncing user community groups")
    sync_user_community_groups(instance.user)
