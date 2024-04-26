import logging

from app.celery import app

from .models import MumbleAccess

logger = logging.getLogger(__name__)


@app.task
def clear_unauthorized_mumble_access():
    for mumble_access in MumbleAccess.objects.all():
        if not mumble_access.user.has_perm("mumble.view_mumbleaccess"):
            logger.info(
                "Clearing mumble access for user %s", mumble_access.user
            )
            mumble_access.delete()
