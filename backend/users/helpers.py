from django.contrib.auth.models import User
from discord.models import DiscordUser
from eveonline.models import EvePrimaryCharacter
from .schemas import (
    UserProfileSchema,
)


def get_user_profile(user_id: int) -> UserProfileSchema:
    user = User.objects.get(id=user_id)
    discord_user = DiscordUser.objects.get(user=user)
    primary_character = EvePrimaryCharacter.objects.get(
        character__token__user=user
    )

    payload = {
        "user_id": user.id,
        "username": user.username,
        "avatar": discord_user.avatar,
        "permissions": [
            f"{p._meta.app_label}.{p.codename}"  # pylint: disable=protected-access
            for p in user.user_permissions.all()
        ],
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "eve_character_profile": {
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
            "alliance_id": (
                primary_character.character.corporation.alliance.alliance_id
                if hasattr(primary_character.character.corporation, "alliance")
                else None
            ),
            "alliance_name": (
                primary_character.character.corporation.alliance.name
                if hasattr(primary_character.character.corporation, "alliance")
                else None
            ),
            "scopes": [scope.name for scope in primary_character.character.token.scopes.all()],
        },
        "discord_user_profile": {
            "id": discord_user.id,
            "discord_tag": discord_user.discord_tag,
            "avatar": f"https://cdn.discordapp.com/avatars/{discord_user.id}/{discord_user.avatar}.png",
        },
    }

    return UserProfileSchema(**payload)
