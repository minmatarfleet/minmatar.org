import logging

from app.celery import app

from eveonline.helpers.characters import user_primary_character

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


@app.task
def set_mumble_usernames():
    total_users = 0
    users_updated = 0
    for mumber_user in MumbleAccess.objects.allI():
        total_users += 1
        if not mumber_user.user:
            logger.warning(
                "Mumble user with no django user: %d", mumber_user.id
            )
            continue
        if not mumber_user.username:
            char = user_primary_character(mumber_user.user)
            if char:
                mumber_user.username = char.character_name
                logger.info("Mumble username set: %s", mumber_user.username)
                users_updated += 1
    logger.info(
        "Updated %d out of %d Mumble usernames", users_updated, total_users
    )
