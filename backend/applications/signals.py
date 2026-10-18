import logging

from django.db import transaction
from django.db.models import signals
from django.dispatch import receiver

from .models import EveCorporationApplication
from .tasks import (
    close_deleted_application_thread_task,
    sync_application_thread_task,
)

logger = logging.getLogger(__name__)


def _enqueue_after_commit(task, *args):
    """Queue `task` once the save commits. A broker outage is logged, not
    raised: the application is already saved."""

    def _enqueue():
        try:
            task.delay(*args)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Could not queue %s%s", task.name, args)

    transaction.on_commit(_enqueue)


@receiver(
    signals.post_save,
    sender=EveCorporationApplication,
    dispatch_uid="eve_corporation_application_post_save",
)
def eve_corporation_application_post_save(
    sender, instance, created, **kwargs
):  # noqa # pylint: disable=unused-argument
    """Queue the forum thread (created on first save) and the accepted /
    rejected notice. Discord is called from Celery after the save commits,
    not from the web request."""
    needs_thread = instance.discord_thread_id is None
    if not needs_thread and instance.status not in ("accepted", "rejected"):
        return
    _enqueue_after_commit(
        sync_application_thread_task, instance.pk, instance.status
    )


@receiver(
    signals.pre_delete,
    sender=EveCorporationApplication,
    dispatch_uid="eve_corporation_application_pre_delete",
)
def eve_corporation_application_pre_delete(
    sender, instance, **kwargs
):  # noqa # pylint: disable=unused-argument
    """Queue closing the forum thread if one exists"""
    if not instance.discord_thread_id:
        return
    _enqueue_after_commit(
        close_deleted_application_thread_task, instance.discord_thread_id
    )
