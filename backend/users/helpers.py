from django.contrib.auth.models import User, Group
from django.db.models import signals

from discord.models import DiscordUser
from eveonline.models import EvePrimaryCharacter

from .schemas import UserProfileSchema


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
    discord_user = DiscordUser.objects.get(user=user)
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
            "scopes": [
                scope.name
                for scope in primary_character.character.token.scopes.all()
            ],
        }
    else:
        eve_character_profile = None

    payload = {
        "user_id": user.id,
        "username": user.username,
        "avatar": discord_user.avatar,
        "permissions": get_user_permissions(user_id),
        "is_superuser": user.is_superuser,
        "eve_character_profile": eve_character_profile,
        "discord_user_profile": {
            "id": discord_user.id,
            "discord_tag": discord_user.discord_tag,
            "avatar": f"https://cdn.discordapp.com/avatars/{discord_user.id}/{discord_user.avatar}.png",
        },
    }

    return UserProfileSchema(**payload)
