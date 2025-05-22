import logging

from app.celery import app

from eveonline.helpers.characters import user_primary_character

from .models import MumbleAccess
from .router import mumble_username

logger = logging.getLogger(__name__)


@app.task
def clear_unauthorized_mumble_access():
    for mumble_access in MumbleAccess.objects.all():
        if not mumble_access.user.has_perm("mumble.view_mumbleaccess"):
            logger.info(
                "Clearing mumble access for user %s", mumble_access.user
            )
            mumble_access.suspended = True
            mumble_access.save()


@app.task
def set_mumble_usernames():
    total_users = 0
    users_updated = 0
    for mumble_user in MumbleAccess.objects.all():
        total_users += 1
        if not mumble_user.user:
            logger.warning(
                "Mumble user with no django user: %d", mumble_user.id
            )
            continue
        if not mumble_user.username:
            char = user_primary_character(mumble_user.user)
            if char:
                mumble_user.username = mumble_username(mumble_user.user)
                mumble_user.save()
                logger.info("Mumble username set: %s", mumble_user.username)
                users_updated += 1
    logger.info(
        "Updated %d out of %d Mumble usernames", users_updated, total_users
    )
