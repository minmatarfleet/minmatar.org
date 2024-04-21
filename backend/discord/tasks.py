import logging
import re

from django.contrib.auth.models import Group, User

from app.celery import app
from discord.client import DiscordClient
from eveonline.models import EveCharacter

from .helpers import get_discord_user, get_expected_nickname
from .models import DiscordRole, DiscordUser

discord = DiscordClient()
logger = logging.getLogger(__name__)


@app.task()
def import_external_roles():
    roles = discord.get_roles()
    for role in roles:
        if role["managed"]:
            continue
        if role["name"] == "@everyone":
            continue
        if not Group.objects.filter(name=role["name"]).exists():
            Group.objects.create(name=role["name"])


@app.task()
def sync_discord_users():
    for user in User.objects.all():
        sync_discord_user(user.id)


@app.task()
def sync_discord_user_nicknames():
    for user in User.objects.all():
        logger.info("Syncing discord nickname user %s", user.username)
        discord_user = DiscordUser.objects.filter(user_id=user.id).first()
        if discord_user is None:
            continue
        expected_nickname = get_expected_nickname(user)
        logger.info("Expected nickname: %s", expected_nickname)
        if expected_nickname is None:
            continue

        if discord_user.nickname != expected_nickname:
            logger.info(
                "Updating nickname for user %s to %s",
                user.username,
                expected_nickname,
            )
            discord.update_user(discord_user.id, nickname=expected_nickname)
            discord_user.nickname = expected_nickname
            discord_user.save()


@app.task(rate_limit="1/s")
def sync_discord_user(user_id: int):
    user = User.objects.get(id=user_id)
    discord_user = DiscordUser.objects.filter(user_id=user.id).first()
    if discord_user is None:
        return
    external_discord_user = get_discord_user(user, notify=True)
    if external_discord_user is None:
        return
    expected_discord_roles = DiscordRole.objects.filter(
        group__in=user.groups.all()
    )
    actual_discord_role_ids = external_discord_user["roles"]

    # add missing tracked roles to the user
    for expected_discord_role in expected_discord_roles:
        if str(expected_discord_role.role_id) not in actual_discord_role_ids:
            logger.warning(
                "User %s missing external role %s that they should have, adding",
                user.username,
                expected_discord_role.name,
            )
            discord.add_user_role(
                discord_user.id, expected_discord_role.role_id
            )
            expected_discord_role.members.add(discord_user)

    # remove excess tracked roles from the user
    for discord_role_id in actual_discord_role_ids:
        discord_role_id = int(discord_role_id)
        if not DiscordRole.objects.filter(role_id=discord_role_id).exists():
            continue
        discord_role = DiscordRole.objects.get(role_id=discord_role_id)
        if discord_role in expected_discord_roles:
            continue
        logger.warning(
            "User %s has external role %s that they should not have, removing",
            user.username,
            discord_role.name,
        )
        discord.remove_user_role(discord_user.id, discord_role_id)
        discord_role.members.remove(discord_user)


@app.task()
def audit_discord_guild_users():
    external_discord_users = discord.get_members()
    for external_discord_user in external_discord_users:
        discord_user_id = int(external_discord_user["user"]["id"])
        if DiscordUser.objects.filter(id=discord_user_id).exists():
            continue

        external_roles = external_discord_user["roles"]
        if len(external_roles) > 0:
            for role_id in external_roles:
                try:
                    discord.remove_user_role(discord_user_id, int(role_id))
                except Exception as e:
                    logger.error(
                        "Error removing role %s from user %s: %s",
                        role_id,
                        discord_user_id,
                        e,
                    )
                    print(external_discord_user)
