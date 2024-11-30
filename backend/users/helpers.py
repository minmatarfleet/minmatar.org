import logging
from typing import List
from django.contrib.auth.models import Group, User
from django.db.models import signals

from discord.models import DiscordUser
from eveonline.models import EvePrimaryCharacter

from .schemas import UserProfileSchema

logger = logging.getLogger(__name__)


def offboard_user(user_id: int):
    signals.m2m_changed.disconnect(
        sender=User.groups.through, dispatch_uid="user_group_changed"
    )
    user = User.objects.get(id=user_id)
    user.delete()


def offboard_group(group_id: int):
    signals.m2m_changed.disconnect(
        sender=User.groups.through, dispatch_uid="user_group_changed"
    )
    group = Group.objects.get(id=group_id)
    group.delete()


def get_user_permissions(user_id: int) -> list[str]:
    user = User.objects.get(id=user_id)
    permissions = user.get_all_permissions()
    return list(permissions)


def get_user_profile(user_id: int) -> UserProfileSchema:
    user = User.objects.get(id=user_id)
    return expand_user_profile(user, True, True)


def expand_user_profile(
    user: User, include_permissions: bool, include_discord: bool
) -> UserProfileSchema:
    if include_discord:
        discord_user = DiscordUser.objects.filter(user=user).first()
    else:
        discord_user = None

    primary_character = EvePrimaryCharacter.objects.filter(
        character__token__user=user
    ).first()
    if primary_character:
        eve_character_profile = {
            "character_id": primary_character.character.character_id,
            "character_name": primary_character.character.character_name,
            "corporation_id": (
                primary_character.character.corporation.corporation_id
                if hasattr(primary_character.character, "corporation")
                else None
            ),
            "corporation_name": (
                primary_character.character.corporation.name
                if hasattr(primary_character.character, "corporation")
                else None
            ),
        }
        if include_permissions:
            scopes = [
                scope.name
                for scope in primary_character.character.token.scopes.all()
            ]
        else:
            scopes = []
        eve_character_profile["scopes"] = scopes
    else:
        eve_character_profile = None

    payload = {
        "user_id": user.id,
        "username": user.username,
        "is_superuser": user.is_superuser,
        "eve_character_profile": eve_character_profile,
    }

    if include_permissions:
        payload["permissions"] = get_user_permissions(user.id)
    else:
        payload["permissions"] = []

    if discord_user:
        payload["avatar"] = (discord_user.avatar,)
        payload["discord_user_profile"] = {
            "id": discord_user.id,
            "discord_tag": discord_user.discord_tag,
            "avatar": f"https://cdn.discordapp.com/avatars/{discord_user.id}/{discord_user.avatar}.png",
        }
    else:
        payload["discord_user_profile"] = None

    return UserProfileSchema(**payload)


def get_user_profiles(user_ids: List[int]) -> List[UserProfileSchema]:
    results = []
    users = User.objects.filter(id__in=user_ids)
    for user in users:
        try:
            results.append(expand_user_profile(user, False, False))
        except Exception:
            logger.error("Error expanding profile for user %d", user.id)
    return results
