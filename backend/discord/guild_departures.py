"""Take every role off people who left a corporation's server's corporation.

Role sync (discord.guild_roles) only adds and removes the mapped roles, so
roles a director handed out by hand stay on someone who left. With
``strip_roles_on_leave`` on, a pass lists the server's members and, for each
linked account whose site user has no character in the corporation and none
in an alliance member corporation, removes every role the bot can remove.

- They stay on the server. Kicking is the member policy's job
  (discord.guild_access).
- Unlinked accounts are never touched: we can't tell who they are.
- Never touched: bots, the server owner, exempted usernames (the member
  policy's list), server staff (Administrator, Manage Server, Kick or Ban
  Members), and anyone whose top role is at or above the bot's.
- Never removed: @everyone, managed roles (bots, boosts, integrations), and
  roles at or above the bot's, which Discord wouldn't let it remove anyway.

A pass that would strip more than ``BRAKE_SHARE`` of the server's people
strips nobody and waits for a director to approve it, as the member policy
does. An approval covers the next pass.

The alliance Discord, Fishermen servers and tribe servers are never touched.
"""

import logging

import requests
from django.db import transaction
from django.utils import timezone
from ratelimit import RateLimitException

from discord.client import DiscordClient
from discord.guild_access import (
    STAFF_PERMISSIONS,
    _brake_limit,
    _Exemptions,
    _top_position,
)
from discord.guild_roles import (
    _apply,
    _held_permissions,
    _mark_cannot_manage,
    _members,
    _owner,
    _permission_lost,
    _protected,
    _read_roles,
    _role_id,
    _role_ids,
    _StopGuild,
    qualifying_user_ids,
)
from discord.models import DiscordGuild, DiscordRoleMapping, DiscordUser

logger = logging.getLogger(__name__)


class StripError(ValueError):
    """A request the form can't act on. `code` is the API detail."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _save(guild: DiscordGuild, **fields) -> None:
    for name, value in fields.items():
        setattr(guild, name, value)
    guild.save(update_fields=[*fields, "updated_at"])


def _clear_hold() -> dict:
    return {
        "roles_strip_held_at": None,
        "roles_strip_held_count": 0,
        "roles_strip_approved_at": None,
    }


def set_strip_on_leave(guild: DiscordGuild, enabled: bool) -> None:
    """Turn the option on or off from the Settings form."""
    enabled = bool(enabled)
    if enabled == guild.strip_roles_on_leave:
        return
    _save(guild, strip_roles_on_leave=enabled, **_clear_hold())
    if enabled:
        transaction.on_commit(lambda: queue_strip(guild.pk))


def approve_strip_hold(guild: DiscordGuild) -> None:
    """Let a held pass go ahead."""
    if guild.roles_strip_held_at is None:
        raise StripError("not_held")
    _save(guild, roles_strip_approved_at=timezone.now())
    transaction.on_commit(lambda: queue_strip(guild.pk))


def queue_strip(guild_pk: int) -> None:
    # guild_departures is imported by discord.tasks; keep this local.
    from discord.tasks import (  # pylint: disable=import-outside-toplevel
        strip_departed_guild_roles,
    )

    strip_departed_guild_roles.delay(guild_pk)


def _read_server(guild: DiscordGuild, client):
    """(bot member, roles, owner id, members), or None when Discord can't
    be read. A lost permission is recorded."""
    loaded = _read_roles(client)
    if isinstance(loaded, BaseException) or loaded is None:
        if isinstance(loaded, BaseException) and _permission_lost(loaded):
            _mark_cannot_manage(guild)
        return None
    bot_member, roles = loaded
    try:
        owner_id = int(client.get_guild().get("owner_id") or 0) or None
        members = _members(client)
    except (requests.RequestException, RateLimitException) as error:
        if _permission_lost(error):
            _mark_cannot_manage(guild)
        else:
            logger.warning(
                "Discord role strip for guild %s failed: %s",
                guild.guild_id,
                error,
            )
        return None
    if not members:
        # An empty list is a failed read, not an empty server.
        return None
    return bot_member, roles, owner_id, members


def _role_table(guild: DiscordGuild, roles: list):
    """(role id -> position, ids of roles the bot may ever remove)."""
    positions = {}
    removable = set()
    for role in roles:
        role_id = _role_id(role)
        if role_id is None:
            continue
        positions[role_id] = int(role.get("position") or 0)
        everyone = role_id == guild.guild_id or role.get("name") == "@everyone"
        if not everyone and not role.get("managed"):
            removable.add(role_id)
    return positions, removable


def _people(members: list) -> list[tuple[int, dict, dict]]:
    """(discord id, user, member) for people, not bots."""
    people = []
    for member in members:
        user = member.get("user") or {}
        if user.get("bot"):
            continue
        try:
            discord_id = int(user["id"])
        except (KeyError, TypeError, ValueError):
            continue
        people.append((discord_id, user, member))
    return people


def _allowed_user_ids(corporation) -> set[int]:
    qualifying = qualifying_user_ids(
        "corporation",
        corporation,
        {
            DiscordRoleMapping.STATE_MEMBER,
            DiscordRoleMapping.STATE_ALLIANCE_MEMBER,
        },
    )
    return set().union(*qualifying.values())


def find_departed(
    guild: DiscordGuild,
    corporation,
    members: list,
    roles: list,
    bot_member: dict,
    owner_id: int | None,
) -> tuple[list[tuple[int, list[int]]], int]:
    """([(discord id, role ids to remove)], how many people are on the
    server). No Discord calls."""
    positions, removable = _role_table(guild, roles)
    bot_top = _top_position(
        {"roles": bot_member.get("roles") or []}, positions
    )
    allowed = _allowed_user_ids(corporation)
    exemptions = _Exemptions(guild)
    people = _people(members)
    linked = dict(
        DiscordUser.objects.filter(
            id__in=[discord_id for discord_id, _, _ in people]
        ).values_list("id", "user_id")
    )

    def kept(discord_id, user, member) -> bool:
        user_id = linked.get(discord_id)
        if user_id is None or user_id in allowed or discord_id == owner_id:
            return True
        username = str(user.get("username") or "").lower()
        if exemptions.match(discord_id, username):
            return True
        if _held_permissions(guild, roles, member) & STAFF_PERMISSIONS:
            return True
        return _top_position(member, positions) >= bot_top

    departed = []
    for discord_id, user, member in people:
        held = _role_ids(member.get("roles"))
        strip = sorted(
            role_id
            for role_id in held
            if role_id in removable and positions.get(role_id, 0) < bot_top
        )
        if strip and not kept(discord_id, user, member):
            departed.append((discord_id, strip))
    return departed, len(people)


def _strip(client, departed) -> int:
    """Remove the roles. Returns how many people lost at least one."""
    stripped = 0
    for discord_id, role_ids in departed:
        removed_any = False
        for role_id in role_ids:
            try:
                problem = _apply(client, discord_id, role_id, add=False)
            except (requests.RequestException, RateLimitException) as error:
                logger.warning(
                    "Discord role strip on guild %s for %s failed: %s",
                    client.guild_id,
                    discord_id,
                    error,
                )
                continue
            removed_any = removed_any or not problem
        stripped += int(removed_any)
    return stripped


def strip_guild(guild: DiscordGuild) -> int | None:
    """One pass over one server. Returns how many people were stripped,
    or None when the pass couldn't run."""
    if (
        not guild.strip_roles_on_leave
        or not guild.is_active
        or not guild.can_manage_roles
        or _protected(guild)
    ):
        return None
    owned = _owner(guild)
    if owned is None or owned[0] != "corporation":
        return None
    corporation = owned[1]

    client = DiscordClient.for_guild(guild.guild_id)
    server = _read_server(guild, client)
    if server is None:
        return None
    bot_member, roles, owner_id, members = server

    now = timezone.now()
    departed, people = find_departed(
        guild, corporation, members, roles, bot_member, owner_id
    )
    approved = guild.roles_strip_approved_at is not None
    if len(departed) > _brake_limit(people) and not approved:
        if guild.roles_strip_held_at is None:
            logger.warning(
                "Discord guild %s role strip held: %s of %s would lose roles",
                guild.guild_id,
                len(departed),
                people,
            )
        _save(
            guild,
            roles_strip_held_at=guild.roles_strip_held_at or now,
            roles_strip_held_count=len(departed),
            roles_strip_checked_at=now,
            roles_strip_last_count=0,
        )
        return 0

    try:
        stripped = _strip(client, departed)
    except _StopGuild:
        _mark_cannot_manage(guild)
        return None
    _save(
        guild,
        roles_strip_checked_at=now,
        roles_strip_last_count=stripped,
        **_clear_hold(),
    )
    if stripped:
        logger.info(
            "Discord guild %s: removed all roles from %s who left",
            guild.guild_id,
            stripped,
        )
    return stripped


def strip_departed_roles(guild_pk: int | None = None) -> None:
    """One pass over every server with the option on, or a single one."""
    queryset = DiscordGuild.objects.filter(
        strip_roles_on_leave=True, can_manage_roles=True, is_active=True
    )
    if guild_pk is not None:
        queryset = DiscordGuild.objects.filter(pk=guild_pk)
    for guild in queryset:
        strip_guild(guild)
