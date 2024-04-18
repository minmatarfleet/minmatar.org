import logging

import requests
from django.contrib.auth.models import User

from discord.client import DiscordClient
from eveonline.models import EveCharacter

from .models import DiscordRole, DiscordUser

discord = DiscordClient()
logger = logging.getLogger(__name__)
DISCORD_PEOPLE_TEAM_CHANNEL_ID = 1098974756356771870


def get_discord_user(user: User, notify=False):
    """
    Fetches a user based on their discord user
    If they don't exist, notifies people team if notify=True
    """
    external_discord_user = None
    if not DiscordUser.objects.filter(user_id=user.id).exists():
        logger.error(
            "Found a user without a DiscordUser connected: %s", user.id
        )
        return None

    discord_user = DiscordUser.objects.get(user_id=user.id)
    try:
        external_discord_user = discord.get_user(discord_user.id)
    except requests.exceptions.HTTPError as e:
        if notify:
            if e.response.json() == {
                "message": "Unknown Member",
                "code": 10007,
            }:
                characters = ",".join(
                    [
                        char.character_name
                        for char in EveCharacter.objects.filter(
                            token__user__id=user.id
                        )
                    ]
                )

                message = "The following user needs to be offboarded,\n"
                message += f"Discord ID: {user.username}\n"
                message += f"Characters: {characters}\n"
                discord.create_message(DISCORD_PEOPLE_TEAM_CHANNEL_ID, message)
                return None

        raise e

    return external_discord_user


def add_user_to_expected_discord_roles(user: User):
    """
    Adds the expected roles to a user
    NOTE: This should not occur, any added roles are a warning / bug
    """
    discord_user = DiscordUser.objects.get(user_id=user.id)
    expected_discord_roles = DiscordRole.objects.filter(
        group__in=user.groups.all()
    )
    for expected_discord_role in expected_discord_roles:
        if discord_user in expected_discord_role.members.all():
            logger.info("User has expected role, skipping")
            continue
        logger.warning(
            "User does not have expected role, adding user %s to external role %s",
            user.username,
            expected_discord_role.name,
        )
        discord.add_user_role(discord_user.id, expected_discord_role.role_id)
        expected_discord_role.members.add(discord_user)
