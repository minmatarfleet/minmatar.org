import logging
import uuid
from typing import List, Optional

import requests
from django.contrib.auth.models import Group, User, Permission
from django.db import IntegrityError, connection, transaction

from discord.client import DiscordClient
from discord.models import (
    DiscordChannelActivityRecord,
    DiscordRole,
    DiscordUser,
)
from discord.sync_context import disable_discord_group_sync
from audit.models import AuditEntry
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation, EvePlayer

from .schemas import EveCharacterSchema, UserProfileSchema

logger = logging.getLogger(__name__)

# Left behind when the mumble Django app was hard-deleted. Production still has
# the table with a non-cascading FK to auth_user, which blocks User.delete().
LEGACY_MUMBLE_ACCESS_TABLE = "mumble_mumbleaccess"


def _delete_legacy_mumble_access(user_id: int) -> None:
    """Delete leftover MumbleAccess rows for this user, if the table exists."""
    if (
        LEGACY_MUMBLE_ACCESS_TABLE
        not in connection.introspection.table_names()
    ):
        return
    quoted = connection.ops.quote_name(LEGACY_MUMBLE_ACCESS_TABLE)
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {quoted} WHERE user_id = %s",
            [user_id],
        )


def offboard_user(user_id: int):
    """
    Delete a user without firing Discord m2m role sync on cascading group clears.

    Uses a scoped skip flag (not a permanent signal disconnect) so the worker
    keeps syncing Discord for other users afterward.
    """
    with disable_discord_group_sync():
        user = User.objects.get(id=user_id)
        _delete_legacy_mumble_access(user_id)
        user.delete()


def offboard_group(group_id: int):
    """
    Delete an auth Group and its Discord role without m2m Discord sync noise.

    Scoped skip only for this delete; Discord sync stays enabled afterward.
    """
    with disable_discord_group_sync():
        group = Group.objects.get(id=group_id)
        # Delete Discord role from server and remove DiscordRole row before
        # deleting Group
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
    # Local import avoids users ↔ groups circular import at module load.
    # pylint: disable-next=import-outside-toplevel
    from groups.helpers.feature_access import (  # noqa: PLC0415
        legacy_permissions_for_profile,
    )

    user = User.objects.get(id=user_id)
    permissions = set(user.get_all_permissions())
    permissions.update(legacy_permissions_for_profile(user))
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
    # Local import avoids users ↔ groups circular import at module load.
    # pylint: disable-next=import-outside-toplevel
    from groups.helpers.feature_access import (  # noqa: PLC0415
        user_community_status,
    )

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
        community_status=user_community_status(user),
        eve_character_profile=eve_character_profile,
        permissions=[],
        discord_user_profile=None,
    )


def expand_user_profile(
    user: User, include_permissions: bool, include_discord: bool
) -> UserProfileSchema:
    # Local import avoids users ↔ groups circular import at module load.
    # pylint: disable-next=import-outside-toplevel
    from groups.helpers.feature_access import (  # noqa: PLC0415
        user_community_status,
    )

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
        "community_status": user_community_status(user),
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

    # The Discord ID is the identity. Usernames can be changed and are then
    # released for someone else to claim, so they must never pick the account.
    discord_user = (
        DiscordUser.objects.filter(id=user["id"])
        .select_related("user")
        .first()
    )
    if discord_user:
        django_user = discord_user.user
        _follow_discord_username(django_user, user["username"])
    else:
        try:
            with transaction.atomic():
                django_user = _create_user_for_discord(user["username"])
                discord_user = DiscordUser.objects.create(
                    id=user["id"], user=django_user, discord_tag=discord_tag
                )
            logger.info(
                "Discord user created: %s %s", discord_user.id, discord_tag
            )
        except IntegrityError:
            # A second first-login for the same Discord ID (double click)
            # got there first; its account is the one to use.
            discord_user = (
                DiscordUser.objects.filter(id=user["id"])
                .select_related("user")
                .first()
            )
            if discord_user is None:
                raise
            django_user = discord_user.user

    discord_user.discord_tag = discord_tag
    discord_user.avatar = user["avatar"]
    discord_user.save()

    ensure_eve_player_for_user(django_user)

    return django_user


def _username_taken(username: str, exclude_user_id=None) -> bool:
    # MySQL compares usernames case-insensitively, so check the same way.
    taken = User.objects.filter(username__iexact=username)
    if exclude_user_id is not None:
        taken = taken.exclude(id=exclude_user_id)
    return taken.exists()


def _create_user_for_discord(discord_username: str) -> User:
    """
    New account for a Discord ID we haven't seen.

    An existing account with the same username belongs to whoever held that
    Discord username before; it is never handed over.
    """
    username = discord_username
    if _username_taken(username):
        username = f"{discord_username}__d{uuid.uuid4().hex[:8]}"
        logger.warning(
            "Discord username %s already belongs to another account; "
            "creating %s instead",
            discord_username,
            username,
        )

    django_user = User.objects.create(username=username)
    logger.info("Django user created: %s", django_user.username)
    AuditEntry.objects.create(
        user=django_user,
        category="user_registered",
        summary=f"User created: {django_user.username}",
    )
    return django_user


def _follow_discord_username(django_user: User, discord_username: str):
    """
    Keep the account username equal to the Discord username after a rename.

    Voice activity is recorded by Discord username and matched on it. If the
    new name is still held by a stale account, keep the current one.
    """
    if django_user.username == discord_username:
        return
    if _username_taken(discord_username, exclude_user_id=django_user.id):
        logger.warning(
            "User %s renamed on Discord to %s, which another account holds",
            django_user.id,
            discord_username,
        )
        return
    logger.info(
        "User %s renamed on Discord: %s -> %s",
        django_user.id,
        django_user.username,
        discord_username,
    )
    old_username = django_user.username
    with transaction.atomic():
        django_user.username = discord_username
        django_user.save(update_fields=["username"])
        # Voice minutes logged under the old name were this pilot's. Move
        # them so they stay theirs, and are not credited to whoever claims
        # the released name next.
        DiscordChannelActivityRecord.objects.filter(
            username=old_username
        ).update(username=discord_username)


def ensure_eve_player_for_user(django_user: User) -> EvePlayer:
    """
    Ensure the user has an EvePlayer.

    Nickname uniqueness is case-insensitive on MySQL (utf8mb4_uca1400_ai_ci),
    so Discord usernames that only differ by case from an existing nickname
    must not break login (including Django admin Discord OAuth).
    """
    existing = EvePlayer.objects.filter(user=django_user).first()
    if existing:
        return existing

    nickname = _unique_eve_player_nickname(django_user)
    try:
        return EvePlayer.objects.create(user=django_user, nickname=nickname)
    except IntegrityError:
        # Race: another request created the row, or nick still collided.
        existing = EvePlayer.objects.filter(user=django_user).first()
        if existing:
            return existing
        nickname = f"{django_user.username}__u{django_user.pk}"
        return EvePlayer.objects.create(user=django_user, nickname=nickname)


def _unique_eve_player_nickname(django_user: User) -> str:
    """Pick a nickname that won't collide case-insensitively with another player."""
    nickname = django_user.username
    if not EvePlayer.objects.filter(nickname__iexact=nickname).exists():
        return nickname
    return f"{django_user.username}__u{django_user.pk}"
