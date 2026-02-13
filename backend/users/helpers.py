import logging
from typing import List, Optional

import requests
from django.contrib.auth.models import Group, User, Permission
from django.db.models import signals

from discord.client import DiscordClient
from discord.models import DiscordRole, DiscordUser
from audit.models import AuditEntry
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation, EvePlayer

from .schemas import EveCharacterSchema, UserProfileSchema

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
    # Delete Discord role from server and remove DiscordRole row before deleting Group
    try:
        discord_role = group.discord_group
        if discord_role.role_id:
            try:
                DiscordClient().delete_role(discord_role.role_id)
            except requests.HTTPError as e:
                logger.warning(
                    "Could not delete Discord role %s (id=%s): %s",
                    discord_role.name,
                    discord_role.role_id,
                    e,
                )
        discord_role.delete()
    except DiscordRole.DoesNotExist:
        pass
    group.delete()


def get_user_permissions(user_id: int) -> list[str]:
    user = User.objects.get(id=user_id)
    permissions = user.get_all_permissions()
    return list(permissions)


def get_user_profile(user_id: int) -> UserProfileSchema:
    user = User.objects.get(id=user_id)
    return expand_user_profile(user, True, True)


def add_user_permission(user: User, permission: str):
    """
    Adds a specific permission to a user

    Primarily used for testing.
    """
    permission = Permission.objects.get(codename=permission)
    user.user_permissions.add(permission)


def _user_profile_from_prefetched(
    user: User,
    *,
    primary_character=None,
    corporation_name: Optional[str] = None,
) -> UserProfileSchema:
    """Build UserProfileSchema from prefetched user/character/corp (no extra queries)."""
    if primary_character is None:
        eve_character_profile = None
    else:
        eve_character_profile = EveCharacterSchema(
            character_id=primary_character.character_id,
            character_name=primary_character.character_name,
            corporation_id=primary_character.corporation_id or 0,
            corporation_name=corporation_name or "",
            scopes=[],
        )

    return UserProfileSchema(
        user_id=user.id,
        username=user.username,
        is_superuser=user.is_superuser,
        eve_character_profile=eve_character_profile,
        permissions=[],
        discord_user_profile=None,
    )


def expand_user_profile(
    user: User, include_permissions: bool, include_discord: bool
) -> UserProfileSchema:
    if include_discord:
        discord_user = DiscordUser.objects.filter(user=user).first()
    else:
        discord_user = None

    primary_character = user_primary_character(user)
    if primary_character:
        corporation_name = None
        if primary_character.corporation_id:
            corporation_name = (
                EveCorporation.objects.filter(
                    corporation_id=primary_character.corporation_id
                )
                .values_list("name", flat=True)
                .first()
            )
        eve_character_profile = {
            "character_id": primary_character.character_id,
            "character_name": primary_character.character_name,
            "corporation_id": primary_character.corporation_id or 0,
            "corporation_name": (corporation_name or ""),
        }
        if include_permissions and primary_character.token:
            scopes = [
                scope.name for scope in primary_character.token.scopes.all()
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
        payload["avatar"] = discord_user.avatar
        payload["discord_user_profile"] = {
            "id": discord_user.id,
            "discord_tag": discord_user.discord_tag,
            "nickname": discord_user.nickname,
            "avatar": f"https://cdn.discordapp.com/avatars/{discord_user.id}/{discord_user.avatar}.png",
        }
    else:
        payload["discord_user_profile"] = None

    return UserProfileSchema(**payload)


def get_user_profiles(user_ids: List[int]) -> List[UserProfileSchema]:
    """Fetch multiple user profiles with minimal queries (no N+1)."""
    if not user_ids:
        return []

    users = User.objects.filter(id__in=user_ids).select_related(
        "eveplayer", "eveplayer__primary_character"
    )
    primary_characters = []
    for user in users:
        player = getattr(user, "eveplayer", None)
        primary_characters.append(player.primary_character if player else None)

    corporation_ids = {
        pc.corporation_id
        for pc in primary_characters
        if pc is not None and pc.corporation_id is not None
    }
    corp_name_by_id = {}
    if corporation_ids:
        corp_name_by_id = dict(
            EveCorporation.objects.filter(
                corporation_id__in=corporation_ids
            ).values_list("corporation_id", "name")
        )

    results = []
    for user, primary_character in zip(users, primary_characters):
        try:
            results.append(
                _user_profile_from_prefetched(
                    user,
                    primary_character=primary_character,
                    corporation_name=(
                        corp_name_by_id.get(primary_character.corporation_id)
                        if primary_character
                        and primary_character.corporation_id
                        else None
                    ),
                )
            )
        except Exception:
            logger.exception("Error expanding profile for user %d", user.id)
    return results


def make_user_objects(user):
    """
    Makes database entities from a Discord user profile

    Only creates entities that don't already exist.
    """
    discord_tag = user["username"] + "#" + user["discriminator"]

    django_user, created = User.objects.get_or_create(
        username=user["username"]
    )
    if created:
        logger.info("Django user created: %s", django_user.username)

        AuditEntry.objects.create(
            user=django_user,
            category="user_registered",
            summary=f"User created: {django_user.username}",
        )

    discord_user, created = DiscordUser.objects.get_or_create(
        id=user["id"],
        defaults={"user": django_user, "discord_tag": discord_tag},
    )
    if created:
        logger.info(
            "Discord user created: %s %s", discord_user.id, discord_tag
        )

    discord_user.discord_tag = discord_tag
    discord_user.avatar = user["avatar"]
    discord_user.save()

    discord_user.user = django_user
    discord_user.save()

    EvePlayer.objects.get_or_create(
        user=django_user, defaults={"nickname": django_user.username}
    )

    return django_user
