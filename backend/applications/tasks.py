"""Celery tasks for corporation applications: the Discord forum thread.

The application signals queue these after the save commits, so a slow or
rate-limited Discord never holds the web request that created, accepted or
rejected an application.
"""

import logging

from django.db import transaction

from app.celery import app

from .discord import (
    create_application_thread,
    notify_application_accepted,
    notify_application_rejected,
    notify_application_thread_deleted,
)
from .models import EveCorporationApplication

logger = logging.getLogger(__name__)

THREAD_CREATE_MAX_RETRIES = 3

DECISION_NOTIFIERS = {
    "accepted": notify_application_accepted,
    "rejected": notify_application_rejected,
}


def _ensure_application_thread(application_id: int):
    """The application with its forum thread, creating the thread if needed.

    The row lock stops two queued tasks for the same application from
    opening two threads. Returns None when the application no longer exists.
    """
    with transaction.atomic():
        application = (
            EveCorporationApplication.objects.select_for_update()
            .filter(pk=application_id)
            .first()
        )
        if application is None or application.discord_thread_id is not None:
            return application
        thread_id = create_application_thread(application)
        # update(), not save(): saving would fire post_save and queue again.
        EveCorporationApplication.objects.filter(pk=application_id).update(
            discord_thread_id=thread_id
        )
        application.discord_thread_id = thread_id
        return application


@app.task(bind=True, max_retries=THREAD_CREATE_MAX_RETRIES)
def sync_application_thread_task(self, application_id: int, status: str):
    """Open the application's forum thread if it has none, then post the
    accepted/rejected notice for `status` (the status the save had)."""
    try:
        application = _ensure_application_thread(application_id)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Could not create the Discord thread for application %s",
            application_id,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * 2**self.request.retries)
        return
    if application is None:
        logger.warning(
            "Application %s no longer exists; no Discord thread update",
            application_id,
        )
        return

    notify = DECISION_NOTIFIERS.get(status)
    if notify is None:
        return
    try:
        notify(application)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Could not post the %s notice for application %s",
            status,
            application_id,
        )


@app.task()
def close_deleted_application_thread_task(discord_thread_id: int):
    """Post the deleted notice in the thread of an application that is gone,
    and close the thread."""
    try:
        notify_application_thread_deleted(discord_thread_id)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error closing discord thread: %s", e)
