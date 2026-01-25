import logging
import requests
from django.contrib.auth.models import User
from django.conf import settings
from discord.client import DiscordClient
from eveonline.models import EveCharacter
from eveonline.helpers.characters import user_primary_character
from users.helpers import offboard_user
from .core import make_nickname
from .models import DiscordRole, DiscordUser

discord = DiscordClient()
logger = logging.getLogger(__name__)
DISCORD_PEOPLE_TEAM_CHANNEL_ID = settings.DISCORD_PEOPLE_TEAM_CHANNEL_ID
DISCORD_TECHNOLOGY_TEAM_CHANNEL_ID = (
    settings.DISCORD_TECHNOLOGY_TEAM_CHANNEL_ID
)


def get_expected_nickname(user: User):
    """
    Hardcoded to particular groups for now,
    more robust solution can come later
    """
    user = User.objects.get(id=user.id)
    valid_user_group_names = ["Alliance", "Associate"]
    user_group_names = [group.name for group in user.groups.all()]
    is_valid_for_nickname = False
    for group in user_group_names:
        if group in valid_user_group_names:
            is_valid_for_nickname = True
    discord_user = DiscordUser.objects.get(user_id=user.id)
    eve_primary_character = user_primary_character(user)

    if not eve_primary_character or not is_valid_for_nickname:
        return None

    return make_nickname(eve_primary_character, discord_user)


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
            offboard_user(user.id)

            message = f":white_check_mark: {user.username} ({characters}) was promoted to Ushra'Khant"
            discord.create_message(DISCORD_PEOPLE_TEAM_CHANNEL_ID, message)
            return None

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


def notify_technology_team(location: str):
    discord.create_message(
        DISCORD_TECHNOLOGY_TEAM_CHANNEL_ID,
        message=f"Encountered error in {location}",
    )


def find_unregistered_guild_members():
    """
    Get guild members from discord who do not have a discord user.
    """
    guild_members = discord.get_members()
    registered_ids = set(DiscordUser.objects.values_list("id", flat=True))
    return [
        member
        for member in guild_members
        if not member["user"].get("bot")
        and int(member["user"]["id"]) not in registered_ids
    ]


def remove_all_roles_from_guild_member(discord_user_id: int):
    """
    Removes all roles from a Discord user on the discord server.
    """
    try:
        guild_user = discord.get_user(discord_user_id)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.info(
                "Discord user %s not found on discord server so roles already removed.",
                discord_user_id,
            )
        return

    guild_user_nick = guild_user["nick"]
    roles = guild_user["roles"]
    if not roles:
        logger.info(
            "No roles found for discord user %s with nickname %s",
            discord_user_id,
            guild_user_nick,
        )
    else:
        for role_id in roles:
            discord.remove_user_role(discord_user_id, role_id)
        logger.info(
            "Removing %s discord roles for discord user %s with nickname %s",
            len(roles),
            discord_user_id,
            guild_user_nick,
        )
