import logging
from discord.client import DiscordClient
from .models import DiscordUser
from django.contrib.auth.models import User
from eveonline.models import EvePrimaryCharacter, EveCharacter
import requests

discord = DiscordClient()
logger = logging.getLogger(__name__)
DISCORD_PEOPLE_TEAM_CHANNEL_ID = 1098974756356771870


def get_discord_user_or_begin_offboarding(user: User):
    """
    Fetches a user based on their discord user
    If they don't exist, deletes their entire account
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
