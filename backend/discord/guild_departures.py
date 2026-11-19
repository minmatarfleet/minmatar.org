"""Take every role off people who left a corporation's server's corporation.

Role sync (discord.guild_roles) only adds and removes the mapped roles, so
roles a director handed out by hand stay on someone who left. With
``strip_roles_on_leave`` on, a pass lists the server's members and flags each
linked account whose site user

- has a character that was in the corporation at some point (its stored
  ESI corporation history), and
- has no character in the corporation now and none in an alliance member
  corporation.

Applicants and guests who were never in the corporation are left alone.
A flagged person who still qualifies after ``member_grace_hours`` (so a new
recruit's corporation can catch up) loses every role the bot can remove, in
one request, and the row keeps which roles were removed so a director can
give them back. Someone who comes back before then is dropped from the list.

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
does. An approval covers the people flagged before it, no more than the
held count, for ``APPROVAL_TTL``; a pass that doesn't finish keeps it.

The alliance Discord, Fishermen servers and tribe servers are never touched.
"""

import logging
from datetime import timedelta

import requests
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from ratelimit import RateLimitException

from discord.client import DiscordClient, discord_error_code
from discord.guild_access import (
    LOST_AFTER,
    ServerPeople,
    _brake_limit,
    read_server,
)
from discord.guild_roles import (
    ADMINISTRATOR,
    MANAGE_ROLES,
    MISSING_PERMISSIONS,
    STOP_CODES,
    UNKNOWN_MEMBER,
    _held_permissions,
    _mark_cannot_manage,
    _owner,
    _protected,
    _role_id,
    _role_ids,
    qualifying_user_ids,
)
from discord.models import DiscordGuild, DiscordRoleMapping, DiscordRoleStrip
from eveonline.models import EveCharacterCorporationHistory

logger = logging.getLogger(__name__)

# An approval nobody used by then no longer counts.
APPROVAL_TTL = timedelta(hours=6)
# How long the record of removed roles is kept.
RECORD_DAYS = 90
AUDIT_REASON = "minmatar.org: left the corporation"


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
    else:
        # The record of what was removed stays; nobody is waiting any more.
        guild.role_strips.filter(stripped_at__isnull=True).delete()


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


def _role_table(guild: DiscordGuild, roles: list):
    """(role id -> name, ids of roles the bot may ever remove)."""
    names = {}
    removable = set()
    for role in roles:
        role_id = _role_id(role)
        if role_id is None:
            continue
        names[role_id] = str(role.get("name") or "")
        everyone = role_id == guild.guild_id or role.get("name") == "@everyone"
        if not everyone and not role.get("managed"):
            removable.add(role_id)
    return names, removable


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


def former_member_user_ids(corporation, user_ids) -> set[int]:
    """The site users among user_ids with a character that was ever in the
    corporation, from the stored ESI corporation history."""
    user_ids = list(user_ids)
    if not user_ids:
        return set()
    rows = EveCharacterCorporationHistory.objects.filter(
        Q(character__user_id__in=user_ids)
        | Q(character__token__user_id__in=user_ids),
        corporation_id=corporation.corporation_id,
    ).values_list("character__user_id", "character__token__user_id")
    wanted = set(user_ids)
    return {
        user_id
        for pair in rows
        for user_id in pair
        if user_id is not None and user_id in wanted
    }


def find_departed(
    guild: DiscordGuild,
    corporation,
    members: list,
    roles: list,
    bot_member: dict,
    owner_id: int | None,
) -> tuple[list[dict], int]:
    """(people who left, how many people are on the server). No Discord
    calls. Each row has discord_id, username, display_name, held (their
    role ids) and strip (the ones to remove)."""
    server = ServerPeople(guild, members, roles, bot_member, owner_id)
    _, removable = _role_table(guild, roles)
    allowed = _allowed_user_ids(corporation)

    candidates = []
    for discord_id, user, member in server.people:
        user_id = server.linked.get(discord_id)
        if user_id is None or user_id in allowed:
            continue
        held = _role_ids(member.get("roles"))
        strip = sorted(
            role_id
            for role_id in held
            if role_id in removable
            and server.positions.get(role_id, 0) < server.bot_top
        )
        if not strip:
            continue
        username = str(user.get("username") or "").lower()
        if server.untouchable(discord_id, username, member):
            continue
        candidates.append((user_id, discord_id, user, member, held, strip))

    former = former_member_user_ids(
        corporation, {row[0] for row in candidates}
    )
    departed = [
        {
            "discord_id": discord_id,
            "username": str(user.get("username") or "").lower()[:32],
            "display_name": str(
                member.get("nick") or user.get("global_name") or ""
            )[:100],
            "held": held,
            "strip": strip,
        }
        for user_id, discord_id, user, member, held, strip in candidates
        if user_id in former
    ]
    return departed, len(server.people)


def _sync_pending(guild: DiscordGuild, departed: list[dict], now) -> list:
    """Make the pending list match this pass. Returns its rows."""
    wanted = {row["discord_id"]: row for row in departed}
    pending = guild.role_strips.filter(stripped_at__isnull=True)
    pending.exclude(discord_id__in=wanted).delete()
    existing = {row.discord_id: row for row in pending}
    for discord_id, row in wanted.items():
        current = existing.get(discord_id)
        if current is None:
            existing[discord_id] = DiscordRoleStrip.objects.create(
                guild=guild,
                discord_id=discord_id,
                username=row["username"],
                display_name=row["display_name"],
                flagged_at=now,
            )
            continue
        changed = [
            field
            for field in ("username", "display_name")
            if getattr(current, field) != row[field]
        ]
        for field in changed:
            setattr(current, field, row[field])
        if changed:
            current.save(update_fields=changed)
    return sorted(existing.values(), key=lambda row: row.flagged_at)


def _approved(guild: DiscordGuild, due: list, now) -> bool:
    """The director's approval covers exactly what they saw: people flagged
    before it, no more of them than the held count, and not too long ago."""
    approved_at = guild.roles_strip_approved_at
    if approved_at is None or now - approved_at > APPROVAL_TTL:
        return False
    if len(due) > guild.roles_strip_held_count:
        return False
    return all(row.flagged_at <= approved_at for row in due)


def _strip(client, guild, due: list, departed: dict, names: dict, now):
    """Remove the roles, one request per person.

    Returns (how many were stripped, whether every due person was dealt
    with, whether the bot lost Manage Roles).
    """
    stripped = 0
    refused = 0
    complete = True
    for row in due:
        info = departed[row.discord_id]
        keep = sorted(info["held"] - set(info["strip"]))
        try:
            client.set_member_roles(row.discord_id, keep, reason=AUDIT_REASON)
        except requests.HTTPError as error:
            code = discord_error_code(error)
            if code == UNKNOWN_MEMBER:
                # They left the server since the member list was read.
                row.delete()
                continue
            if code == MISSING_PERMISSIONS:
                # They outrank the bot now; the next pass tries again. On
                # LOST_AFTER in a row the bot has lost Manage Roles.
                complete = False
                refused += 1
                if refused >= LOST_AFTER:
                    return stripped, False, True
                continue
            if code in STOP_CODES:
                return stripped, False, True
            logger.warning(
                "Discord role strip on guild %s stopped at %s: %s",
                guild.guild_id,
                row.discord_id,
                error,
            )
            return stripped, False, False
        except (requests.RequestException, RateLimitException) as error:
            logger.warning(
                "Discord role strip on guild %s stopped at %s: %s",
                guild.guild_id,
                row.discord_id,
                error,
            )
            return stripped, False, False
        refused = 0
        row.stripped_at = now
        row.roles = [
            {"id": str(role_id), "name": names.get(role_id, "")}
            for role_id in info["strip"]
        ]
        row.save(update_fields=["stripped_at", "roles"])
        logger.info(
            "Discord guild %s: removed roles %s from %s, who left",
            guild.guild_id,
            info["strip"],
            row.discord_id,
        )
        stripped += 1
    return stripped, complete, False


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
    server = read_server(guild, client, _mark_cannot_manage, "role strip")
    if server is None:
        return None
    bot_member, roles, owner_id, members = server
    if not _held_permissions(guild, roles, bot_member) & (
        ADMINISTRATOR | MANAGE_ROLES
    ):
        # Someone took Manage Roles away; Settings asks to add the bot again.
        _mark_cannot_manage(guild)
        return None

    now = timezone.now()
    guild.role_strips.filter(
        stripped_at__lt=now - timedelta(days=RECORD_DAYS)
    ).delete()
    departed, people = find_departed(
        guild, corporation, members, roles, bot_member, owner_id
    )
    pending = _sync_pending(guild, departed, now)
    grace = timedelta(hours=guild.member_grace_hours)
    due = [row for row in pending if row.flagged_at + grace <= now]

    if len(due) > _brake_limit(people) and not _approved(guild, due, now):
        if guild.roles_strip_held_at is None:
            logger.warning(
                "Discord guild %s role strip held: %s of %s would lose roles",
                guild.guild_id,
                len(due),
                people,
            )
        _save(
            guild,
            roles_strip_held_at=guild.roles_strip_held_at or now,
            roles_strip_held_count=len(due),
            # A new count needs a new approval.
            roles_strip_approved_at=None,
            roles_strip_checked_at=now,
            roles_strip_last_count=0,
        )
        return 0

    names, _ = _role_table(guild, roles)
    by_id = {row["discord_id"]: row for row in departed}
    stripped, complete, lost = _strip(client, guild, due, by_id, names, now)
    if lost:
        _mark_cannot_manage(guild)
    # A pass that didn't finish keeps the hold and the approval, so the
    # rest go on the next pass without a second approval.
    _save(
        guild,
        roles_strip_checked_at=now,
        roles_strip_last_count=stripped,
        **(_clear_hold() if complete else {}),
    )
    if stripped:
        logger.info(
            "Discord guild %s: removed all roles from %s who left",
            guild.guild_id,
            stripped,
        )
    return None if lost else stripped


def strip_departed_roles(guild_pk: int | None = None) -> None:
    """One pass over every server with the option on, or a single one."""
    queryset = DiscordGuild.objects.filter(
        strip_roles_on_leave=True, can_manage_roles=True, is_active=True
    )
    if guild_pk is not None:
        queryset = DiscordGuild.objects.filter(pk=guild_pk)
    for guild in queryset:
        strip_guild(guild)
