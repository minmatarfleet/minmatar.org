import logging

from django.db.models import signals
from django.dispatch import receiver

from .discord import (
    create_application_thread,
    notify_application_accepted,
    notify_application_deleted,
    notify_application_rejected,
)
from .models import EveCorporationApplication

logger = logging.getLogger(__name__)


@receiver(
    signals.post_save,
    sender=EveCorporationApplication,
    dispatch_uid="eve_corporation_application_post_save",
)
def eve_corporation_application_post_save(
    sender, instance, created, **kwargs
):  # noqa # pylint: disable=unused-argument
    """Create a forum thread when an application is created"""
    if instance.discord_thread_id is None:
        instance.discord_thread_id = create_application_thread(instance)
        instance.save()

    if instance.status == "accepted":
        notify_application_accepted(instance)

    if instance.status == "rejected":
        notify_application_rejected(instance)


@receiver(
    signals.pre_delete,
    sender=EveCorporationApplication,
    dispatch_uid="eve_corporation_application_pre_delete",
)
def eve_corporation_application_pre_delete(
    sender, instance, **kwargs
):  # noqa # pylint: disable=unused-argument
    """Close the forum thread if one exists"""
    try:
        if instance.discord_thread_id:
            notify_application_deleted(instance)
    except Exception as e:
        logger.error("Error closing discord thread: %s", e)
