"""Map existing Discord roles on a corporation or tribe server.

The alliance Discord and a Fishermen server are not mapped here. This module
adds and removes mapped roles for linked accounts. It does not kick anyone,
and it does not create, rename, or delete roles.
"""

import logging

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from ratelimit import RateLimitException

from discord.client import DiscordClient, discord_error_code
from discord.models import DiscordGuild, DiscordRoleMapping, DiscordUser
from eveonline.constants import FL33T_MEMBER_ALLIANCE_IDS
from eveonline.models import EveCharacter, EveCorporation
from tribes.models import Tribe, TribeGroupMembership

logger = logging.getLogger(__name__)

# Discord permission and error codes.
ADMINISTRATOR = 1 << 3
MANAGE_ROLES = 1 << 28
MISSING_ACCESS = 50001
MISSING_PERMISSIONS = 50013
UNKNOWN_GUILD = 10004
UNKNOWN_MEMBER = 10007
UNKNOWN_ROLE = 10011

# A call that means this server can no longer be managed.
STOP_CODES = {
    MISSING_ACCESS,
    MISSING_PERMISSIONS,
    UNKNOWN_GUILD,
    UNKNOWN_MEMBER,
}

CORPORATION_STATES = (
    DiscordRoleMapping.STATE_MEMBER,
    DiscordRoleMapping.STATE_DIRECTOR,
    DiscordRoleMapping.STATE_RECRUITER,
    DiscordRoleMapping.STATE_STRUCTURE_MANAGER,
    DiscordRoleMapping.STATE_ALLIANCE_MEMBER,
)
TRIBE_STATES = (
    DiscordRoleMapping.STATE_MEMBER,
    DiscordRoleMapping.STATE_ALLIANCE_MEMBER,
)

# Office states belong to a corporation. A tribe save cannot include them.
CORPORATION_ONLY_STATES = frozenset(CORPORATION_STATES) - frozenset(
    TRIBE_STATES
)


class MappingError(ValueError):
    """A role mapping the form cannot save. `code` is the API detail."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class _StopGuild(Exception):
    """This server's bot can no longer edit roles. Stop the pass."""


def install_block_reason(
    guild_id, *, corporation_id=None, tribe_id=None
) -> str | None:
    """Why this install must not exchange its OAuth code, or None.

    Exchanging the code adds the bot. On a server the bot is already in,
    that resets the bot's managed role to whatever the URL requested, so a
    protected server is refused before the exchange. `missing_guild` is
    refused for the same reason: an empty guild id used to fall through
    and exchange anyway.
    """
    try:
        parsed = int(guild_id or 0)
    except (TypeError, ValueError):
        return "missing_guild"
    if not parsed:
        return "missing_guild"
    if parsed == int(settings.DISCORD_GUILD_ID or 0):
        return "alliance_server"
    if DiscordGuild.objects.filter(guild_id=parsed, is_primary=True).exists():
        return "alliance_server"
    if DiscordGuild.objects.filter(
        guild_id=parsed, tribe_group_bindings__isnull=False
    ).exists():
        return "alliance_server"
    corporations = EveCorporation.objects.filter(
        discord_guild__guild_id=parsed
    )
    if corporation_id is not None:
        corporations = corporations.exclude(corporation_id=corporation_id)
    if corporations.exists():
        return "guild_taken"
    tribes = Tribe.objects.filter(discord_guild__guild_id=parsed)
    if tribe_id is not None:
        tribes = tribes.exclude(pk=tribe_id)
    if tribes.exists():
        return "guild_taken"
    return None


def _protected(guild: DiscordGuild) -> bool:
    """Alliance Discord or a Fishermen server. Never pass one to for_guild
    from this module."""
    if guild.is_primary or guild.guild_id == int(
        settings.DISCORD_GUILD_ID or 0
    ):
        return True
    return guild.tribe_group_bindings.exists()


def _owner(guild: DiscordGuild):
    """The one corporation or tribe this server belongs to, else None."""
    corporations = list(guild.corporations.all()[:2])
    tribes = list(guild.tribes.all()[:2])
    if len(corporations) + len(tribes) != 1:
        return None
    if corporations:
        return "corporation", corporations[0]
    return "tribe", tribes[0]


def clear_role_mappings(guild: DiscordGuild | None) -> None:
    """Drop mappings once nothing on the site still points at the server."""
    if guild is None:
        return
    if guild.corporations.exists() or guild.tribes.exists():
        return
    guild.role_mappings.all().delete()


def _bits(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _mark_cannot_manage(guild: DiscordGuild) -> None:
    guild.can_manage_roles = False
    guild.roles_checked_at = timezone.now()
    guild.save(
        update_fields=["can_manage_roles", "roles_checked_at", "updated_at"]
    )


def _permission_lost(error: BaseException) -> bool:
    if not isinstance(error, requests.HTTPError):
        return False
    status = error.response.status_code if error.response is not None else None
    return discord_error_code(error) in STOP_CODES or status in (401, 403, 404)


def _read_roles(client):
    """The bot's member record and the server's roles, or an exception."""
    try:
        me = client.get_current_user()
        member = client.get_user(me["id"])
        roles = client.get_roles()
    except (requests.RequestException, RateLimitException) as error:
        return error
    if not isinstance(roles, list) or not isinstance(member, dict):
        return None
    return member, roles


def _role_id(role) -> int | None:
    try:
        return int(role["id"])
    except (KeyError, TypeError, ValueError):
        return None


def _catalog(guild: DiscordGuild, roles: list, member: dict):
    bot_role_ids = {int(role_id) for role_id in member.get("roles") or []}
    positions = [
        int(role.get("position") or 0)
        for role in roles
        if _role_id(role) in bot_role_ids
    ]
    bot_position = max(positions, default=0)
    permissions = _bits(member.get("permissions"))
    can_manage = bool(
        permissions & ADMINISTRATOR or permissions & MANAGE_ROLES
    )
    rows = []
    for role in roles:
        role_id = _role_id(role)
        if role_id is None:
            continue
        position = int(role.get("position") or 0)
        managed = bool(role.get("managed"))
        everyone = role_id == guild.guild_id or role.get("name") == "@everyone"
        rows.append(
            {
                "id": str(role_id),
                "name": str(role.get("name") or "")[:100],
                "position": position,
                "managed": managed,
                "assignable": (
                    can_manage
                    and not everyone
                    and not managed
                    and position < bot_position
                ),
            }
        )
    rows.sort(key=lambda row: row["position"], reverse=True)
    return rows, can_manage


def snapshot_guild_roles(guild: DiscordGuild, client=None) -> bool:
    """Store the roles this bot can assign, and whether it may edit roles.

    Page views read the stored rows. A protected server is left untouched.
    A permission failure is recorded so the form can ask for the bot again.
    Discord being down leaves the previous snapshot in place. `client` is
    the guild's client; the corporation invite refresh passes the one it
    already built.
    """
    if _protected(guild):
        logger.warning(
            "Not reading roles on protected Discord guild %s", guild.guild_id
        )
        return False
    if client is None:
        client = DiscordClient.for_guild(guild.guild_id)
    loaded = _read_roles(client)
    if isinstance(loaded, BaseException):
        if _permission_lost(loaded):
            _mark_cannot_manage(guild)
        else:
            logger.warning(
                "Discord role snapshot for guild %s failed: %s",
                guild.guild_id,
                loaded,
            )
        return False
    if loaded is None:
        return False
    member, roles = loaded
    rows, can_manage = _catalog(guild, roles, member)
    guild.roles = rows
    guild.can_manage_roles = can_manage
    guild.roles_checked_at = timezone.now()
    guild.save(
        update_fields=[
            "roles",
            "can_manage_roles",
            "roles_checked_at",
            "updated_at",
        ]
    )
    _refresh_mapping_problems(guild, {int(row["id"]): row for row in rows})
    return True


def _refresh_mapping_problems(guild: DiscordGuild, by_id: dict) -> None:
    for mapping in guild.role_mappings.all():
        row = by_id.get(mapping.role_id)
        if row is None:
            problem = DiscordRoleMapping.PROBLEM_MISSING
        elif not row["assignable"]:
            problem = DiscordRoleMapping.PROBLEM_ABOVE_BOT
        else:
            problem = ""
        if mapping.problem != problem:
            mapping.problem = problem
            mapping.save(update_fields=["problem", "updated_at"])


def _known_role_ids(guild: DiscordGuild) -> set[int]:
    ids = set()
    for row in guild.roles or []:
        try:
            ids.add(int(row["id"]))
        except (KeyError, TypeError, ValueError):
            continue
    return ids


def replace_role_mappings(
    guild: DiscordGuild, rows: list, allowed: set[str]
) -> None:
    """Replace this server's mappings with the form. Empty role clears a state."""
    if not guild.can_manage_roles or guild.roles_checked_at is None:
        raise MappingError("cannot_manage_roles")
    known = _known_role_ids(guild)
    chosen: dict[str, int] = {}
    for row in rows:
        state = getattr(row, "state", None) or (
            row.get("state") if isinstance(row, dict) else None
        )
        role_id = (
            getattr(row, "role_id", None)
            if not isinstance(row, dict)
            else row.get("role_id")
        )
        if state not in allowed:
            raise MappingError("state_not_allowed")
        if role_id in (None, ""):
            continue
        try:
            parsed = int(role_id)
        except (TypeError, ValueError) as exc:
            raise MappingError("unknown_role") from exc
        if parsed not in known:
            raise MappingError("unknown_role")
        if parsed in chosen.values():
            raise MappingError("duplicate_role")
        chosen[state] = parsed

    with transaction.atomic():
        guild.role_mappings.all().delete()
        DiscordRoleMapping.objects.bulk_create(
            [
                DiscordRoleMapping(guild=guild, state=state, role_id=role_id)
                for state, role_id in chosen.items()
            ]
        )
    transaction.on_commit(lambda: _queue_reconcile(guild.pk))


def _queue_reconcile(guild_pk: int) -> None:
    # guild_roles is imported by discord.tasks, so this import stays local.
    from discord.tasks import (  # pylint: disable=import-outside-toplevel
        reconcile_guild_role_mappings as reconcile_task,
    )

    reconcile_task.delay(guild_pk)


def tribe_bot_configured() -> bool:
    return bool(
        settings.DISCORD_CLIENT_ID and settings.DISCORD_TRIBE_BOT_REDIRECT_URL
    )


def link_tribe_guild(tribe: Tribe, guild: dict) -> int | None:
    """Point the tribe at the server the bot was just added to.

    Returns the previous server id when the tribe moved, so the caller
    can release it. Does not call Discord.
    """
    guild_id = int(guild["id"])
    blocked = install_block_reason(guild_id, tribe_id=tribe.pk)
    if blocked:
        raise MappingError(blocked)
    row, _ = DiscordGuild.objects.update_or_create(
        guild_id=guild_id,
        defaults={
            "name": str(guild.get("name") or "")[:255] or str(guild_id),
            "is_active": True,
            "last_seen_at": timezone.now(),
        },
    )
    previous_id = None
    if tribe.discord_guild_id and tribe.discord_guild_id != row.pk:
        previous_id = tribe.discord_guild.guild_id
    tribe.discord_guild = row
    tribe.save(update_fields=["discord_guild", "updated_at"])
    if previous_id is not None:
        old = DiscordGuild.objects.filter(guild_id=previous_id).first()
        clear_role_mappings(old)
    return previous_id


def unlink_tribe_guild(tribe: Tribe) -> int | None:
    """Drop the tribe's server. Returns its guild id when there was one."""
    guild = tribe.discord_guild
    if guild is None:
        return None
    guild_id = guild.guild_id
    tribe.discord_guild = None
    tribe.save(update_fields=["discord_guild", "updated_at"])
    clear_role_mappings(guild)
    return guild_id


def tribe_discord_settings(tribe: Tribe) -> dict:
    guild = tribe.discord_guild
    payload = role_sync_payload(guild)
    return {
        "available": tribe_bot_configured(),
        "connected": guild is not None,
        "guild_name": guild.name if guild else None,
        **payload,
    }


def queue_snapshot(guild_pk: int) -> None:
    # guild_roles is imported by discord.tasks, so this import stays local.
    from discord.tasks import (  # pylint: disable=import-outside-toplevel
        snapshot_guild_roles_task,
    )

    snapshot_guild_roles_task.delay(guild_pk)


def role_sync_payload(guild: DiscordGuild | None) -> dict:
    """What the settings form reads. No Discord calls."""
    if guild is None:
        return {
            "can_manage_roles": False,
            "checked": False,
            "roles": [],
            "mappings": [],
        }
    mapped = {
        mapping.role_id: mapping for mapping in guild.role_mappings.all()
    }
    roles = []
    for row in guild.roles or []:
        try:
            role_id = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if row.get("assignable") or role_id in mapped:
            roles.append(
                {"id": str(role_id), "name": row.get("name") or str(role_id)}
            )
    return {
        "can_manage_roles": bool(guild.can_manage_roles),
        "checked": guild.roles_checked_at is not None,
        "roles": roles,
        "mappings": [
            {
                "state": mapping.state,
                "role_id": str(mapping.role_id),
                "problem": mapping.problem or None,
            }
            for mapping in mapped.values()
        ],
    }


def _character_user_ids(**filters) -> set[int]:
    return set(
        EveCharacter.objects.filter(
            user_id__isnull=False, **filters
        ).values_list("user_id", flat=True)
    )


def qualifying_user_ids(
    kind: str, owner, states: set[str]
) -> dict[str, set[int]]:
    """Site users who should hold each mapped state. Not an auth.Group source."""
    result: dict[str, set[int]] = {}
    if DiscordRoleMapping.STATE_ALLIANCE_MEMBER in states:
        result[DiscordRoleMapping.STATE_ALLIANCE_MEMBER] = _character_user_ids(
            alliance_id__in=FL33T_MEMBER_ALLIANCE_IDS
        )
    if kind == "corporation":
        if DiscordRoleMapping.STATE_MEMBER in states:
            result[DiscordRoleMapping.STATE_MEMBER] = _character_user_ids(
                corporation_id=owner.corporation_id
            )
        offices = (
            (DiscordRoleMapping.STATE_DIRECTOR, "directors"),
            (DiscordRoleMapping.STATE_RECRUITER, "recruiters"),
            (DiscordRoleMapping.STATE_STRUCTURE_MANAGER, "stewards"),
        )
        for state, field in offices:
            if state not in states:
                continue
            result[state] = set(
                getattr(owner, field)
                .filter(user_id__isnull=False)
                .values_list("user_id", flat=True)
            )
        return result
    if kind == "tribe":
        if DiscordRoleMapping.STATE_MEMBER in states:
            result[DiscordRoleMapping.STATE_MEMBER] = set(
                TribeGroupMembership.objects.filter(
                    tribe_group__tribe_id=owner.pk,
                    status=TribeGroupMembership.STATUS_ACTIVE,
                ).values_list("user_id", flat=True)
            )
        return result
    raise MappingError("state_not_allowed")


def _members(client) -> list:
    try:
        return client.get_members()
    except IndexError:
        # get_members indexes the last page. An empty page used to raise.
        logger.warning(
            "Discord member list for guild %s ended early", client.guild_id
        )
        return []


def _apply(client, discord_id: int, role_id: int, add: bool) -> str:
    try:
        if add:
            client.add_user_role(discord_id, role_id)
        else:
            client.remove_user_role(discord_id, role_id)
    except requests.HTTPError as error:
        code = discord_error_code(error)
        if code == UNKNOWN_ROLE:
            return DiscordRoleMapping.PROBLEM_MISSING
        if code == MISSING_PERMISSIONS:
            return DiscordRoleMapping.PROBLEM_ABOVE_BOT
        if code in STOP_CODES:
            raise _StopGuild() from error
        raise
    return ""


def _role_ids(values) -> set[int]:
    parsed = set()
    for role_id in values or []:
        try:
            parsed.add(int(role_id))
        except (TypeError, ValueError):
            continue
    return parsed


def _accounts(members: list) -> list[tuple[int, set[int], int | None]]:
    """(discord id, role ids, site user id) for people, not bots."""
    parsed = []
    discord_ids = []
    for member in members:
        user = member.get("user") or {}
        if user.get("bot"):
            continue
        try:
            discord_id = int(user["id"])
        except (KeyError, TypeError, ValueError):
            continue
        discord_ids.append(discord_id)
        parsed.append((discord_id, _role_ids(member.get("roles"))))
    linked = dict(
        DiscordUser.objects.filter(id__in=discord_ids).values_list(
            "id", "user_id"
        )
    )
    return [
        (discord_id, current, linked.get(discord_id))
        for discord_id, current in parsed
    ]


def _sync_account(
    client,
    discord_id: int,
    user_id: int,
    current: set[int],
    mappings,
    qualifying: dict,
    problems: dict,
    failed: set,
) -> tuple[int, int]:
    adds = 0
    removes = 0
    for mapping in mappings:
        should = user_id in qualifying.get(mapping.state, set())
        if should == (mapping.role_id in current):
            continue
        problem = _apply(client, discord_id, mapping.role_id, should)
        if problem:
            problems[mapping.pk] = problem
            failed.add(mapping.pk)
            continue
        if mapping.pk not in failed:
            problems[mapping.pk] = ""
        adds += int(should)
        removes += int(not should)
    return adds, removes


def _save_problems(mappings, problems: dict) -> None:
    for mapping in mappings:
        problem = problems.get(mapping.pk, "")
        if mapping.problem != problem:
            mapping.problem = problem
            mapping.save(update_fields=["problem", "updated_at"])


def _load_members(guild: DiscordGuild, client):
    try:
        return _members(client)
    except requests.HTTPError as error:
        if discord_error_code(error) in STOP_CODES:
            _mark_cannot_manage(guild)
            return None
        raise
    except (requests.RequestException, RateLimitException) as error:
        logger.warning(
            "Discord role reconcile for guild %s failed: %s",
            guild.guild_id,
            error,
        )
        return None


def reconcile_guild(guild: DiscordGuild) -> None:
    """Add and remove mapped roles for linked accounts on this one server."""
    if _protected(guild) or not guild.can_manage_roles or not guild.is_active:
        return
    mappings = list(guild.role_mappings.all())
    if not mappings:
        return
    owned = _owner(guild)
    if owned is None:
        logger.warning(
            "Discord guild %s has role mappings and no single owner",
            guild.guild_id,
        )
        return
    kind, owner = owned
    qualifying = qualifying_user_ids(
        kind, owner, {mapping.state for mapping in mappings}
    )
    client = DiscordClient.for_guild(guild.guild_id)
    members = _load_members(guild, client)
    if members is None:
        return

    problems = {mapping.pk: mapping.problem for mapping in mappings}
    failed: set[int] = set()
    adds = 0
    removes = 0
    try:
        for discord_id, current, user_id in _accounts(members):
            if user_id is None:
                continue
            added, removed = _sync_account(
                client,
                discord_id,
                user_id,
                current,
                mappings,
                qualifying,
                problems,
                failed,
            )
            adds += added
            removes += removed
    except _StopGuild:
        _mark_cannot_manage(guild)
        return

    _save_problems(mappings, problems)
    if adds or removes:
        logger.info(
            "Discord guild %s role mappings: %s added, %s removed",
            guild.guild_id,
            adds,
            removes,
        )


def reconcile_guild_role_mappings(guild_pk: int | None = None) -> None:
    """One pass over owned servers that have mappings, or a single server."""
    queryset = (
        DiscordGuild.objects.filter(can_manage_roles=True, is_active=True)
        .filter(role_mappings__isnull=False)
        .distinct()
    )
    if guild_pk is not None:
        queryset = DiscordGuild.objects.filter(pk=guild_pk)
    for guild in queryset:
        reconcile_guild(guild)
