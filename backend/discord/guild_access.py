"""Who may stay on a corporation's Discord server.

A director picks a member policy in Settings: corporation members only, or
alliance members only. An hourly pass lists the server's members and:

- flags anyone who doesn't qualify onto a pending list, with a reason;
- drops them from the list the moment they qualify (they linked their
  Discord on the site, or their character's corporation caught up), leave,
  or are exempted;
- removes them once they've been on the list for ``member_grace_hours``.

So turning a policy on never removes anyone straight away, a newcomer has
the grace period to link their account, and the Settings tab shows who is
about to go so a director can exempt them first.

Never removed: bots, the server owner, exempted usernames, and server staff
(Administrator, Manage Server, Kick or Ban Members, or a role at or above
the bot's, which Discord wouldn't let it remove anyway).

A pass that would remove more than ``BRAKE_SHARE`` of the server's people
(and more than ``BRAKE_MIN``) removes nobody and waits for a director to
approve it. That stops a site data problem from emptying a server.

The alliance Discord and Fishermen servers are never touched.
"""

import logging
import re
from datetime import timedelta

import requests
from django.db import transaction
from django.utils import timezone
from ratelimit import RateLimitException

from discord.client import DiscordClient, discord_error_code
from discord.guild_roles import (
    ADMINISTRATOR,
    KICK_MEMBERS,
    MISSING_PERMISSIONS,
    STOP_CODES,
    _held_permissions,
    _members,
    _owner,
    _permission_lost,
    _protected,
    _read_roles,
    _role_id,
    _role_ids,
    qualifying_user_ids,
)
from discord.models import (
    DiscordGuild,
    DiscordGuildExemption,
    DiscordGuildRemoval,
    DiscordRoleMapping,
    DiscordUser,
)

logger = logging.getLogger(__name__)

BAN_MEMBERS = 1 << 2
MANAGE_GUILD = 1 << 5
STAFF_PERMISSIONS = ADMINISTRATOR | KICK_MEMBERS | BAN_MEMBERS | MANAGE_GUILD

GRACE_HOURS = (1, 24, 72, 168)
DEFAULT_GRACE_HOURS = 24
MAX_EXEMPTIONS = 200
# Hold a pass that would remove more than this share of the server's people.
BRAKE_SHARE = 0.25
BRAKE_MIN = 10
# The pending list the Settings tab shows.
PENDING_LIMIT = 100
# Missing Permissions on one kick means that person outranks the bot. On
# this many in a row, the bot has lost Kick Members.
LOST_AFTER = 3

# Discord usernames since 2023: 2-32 of a-z, 0-9, "_" and ".".
USERNAME = re.compile(r"^[a-z0-9_.]{2,32}$")


class AccessError(ValueError):
    """A member policy the form can't save. `code` is the API detail."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def normalize_username(raw) -> str | None:
    """A Discord username as typed ("@Name", " name ") or None if invalid."""
    name = str(raw or "").strip().lstrip("@").strip().lower()
    return name if USERNAME.match(name) else None


def save_member_policy(
    guild: DiscordGuild,
    policy: str,
    grace_hours: int,
    usernames: list,
    user=None,
) -> None:
    """Replace the policy and the exemption list from the Settings form."""
    if policy not in {
        DiscordGuild.MEMBER_POLICY_OFF,
        DiscordGuild.MEMBER_POLICY_CORPORATION,
        DiscordGuild.MEMBER_POLICY_ALLIANCE,
    }:
        raise AccessError("invalid_policy")
    if grace_hours not in GRACE_HOURS:
        raise AccessError("invalid_grace")
    names = []
    for raw in usernames:
        if not str(raw or "").strip():
            continue
        name = normalize_username(raw)
        if name is None:
            raise AccessError("invalid_username")
        if name not in names:
            names.append(name)
    if len(names) > MAX_EXEMPTIONS:
        raise AccessError("too_many_exemptions")
    if policy and not guild.can_kick_members:
        raise AccessError("cannot_kick_members")

    with transaction.atomic():
        changed = policy != guild.member_policy
        guild.member_policy = policy
        guild.member_grace_hours = grace_hours
        fields = ["member_policy", "member_grace_hours", "updated_at"]
        if changed:
            # A new policy starts a fresh list; its grace starts now.
            guild.member_removals.all().delete()
            guild.members_held_at = None
            guild.members_held_count = 0
            guild.members_approved_at = None
            fields += [
                "members_held_at",
                "members_held_count",
                "members_approved_at",
            ]
        guild.save(update_fields=fields)
        guild.member_exemptions.exclude(username__in=names).delete()
        kept = set(guild.member_exemptions.values_list("username", flat=True))
        DiscordGuildExemption.objects.bulk_create(
            [
                DiscordGuildExemption(
                    guild=guild, username=name, created_by=user
                )
                for name in names
                if name not in kept
            ]
        )
        guild.member_removals.filter(username__in=names).delete()
    if policy:
        transaction.on_commit(lambda: queue_enforce(guild.pk))


def exempt_pending(guild: DiscordGuild, discord_id: int, user=None) -> None:
    """Exempt someone from the pending list (the row's Keep button)."""
    row = guild.member_removals.filter(discord_id=discord_id).first()
    if row is None:
        raise AccessError("not_pending")
    with transaction.atomic():
        name = normalize_username(row.username) or str(row.discord_id)[:32]
        exemption, _ = DiscordGuildExemption.objects.get_or_create(
            guild=guild,
            username=name,
            defaults={"created_by": user, "discord_id": row.discord_id},
        )
        if exemption.discord_id is None:
            exemption.discord_id = row.discord_id
            exemption.save(update_fields=["discord_id"])
        row.delete()


def approve_held(guild: DiscordGuild) -> None:
    """Let a held pass go ahead: removes everyone flagged so far."""
    if guild.members_held_at is None:
        raise AccessError("not_held")
    guild.members_approved_at = timezone.now()
    guild.save(update_fields=["members_approved_at", "updated_at"])
    transaction.on_commit(lambda: queue_enforce(guild.pk))


def queue_enforce(guild_pk: int) -> None:
    # guild_access is imported by discord.tasks, so this import stays local.
    from discord.tasks import (  # pylint: disable=import-outside-toplevel
        enforce_guild_member_policy,
    )

    enforce_guild_member_policy.delay(guild_pk)


def member_access_payload(guild: DiscordGuild | None) -> dict:
    """What the Settings form reads. No Discord calls."""
    if guild is None:
        return {
            "policy": None,
            "grace_hours": DEFAULT_GRACE_HOURS,
            "grace_choices": list(GRACE_HOURS),
            "can_kick_members": False,
            "checked_at": None,
            "last_removed": 0,
            "held": None,
            "exemptions": [],
            "pending": [],
            "pending_total": 0,
        }
    grace = timedelta(hours=guild.member_grace_hours)
    rows = list(guild.member_removals.all()[:PENDING_LIMIT])
    held = None
    if guild.members_held_at is not None:
        held = {
            "since": guild.members_held_at,
            "count": guild.members_held_count,
            "approved": guild.members_approved_at is not None,
        }
    return {
        "policy": guild.member_policy or None,
        "grace_hours": guild.member_grace_hours,
        "grace_choices": list(GRACE_HOURS),
        "can_kick_members": bool(guild.can_kick_members),
        "checked_at": guild.members_checked_at,
        "last_removed": guild.members_last_removed,
        "held": held,
        "exemptions": [
            {
                "username": exemption.username,
                "seen": exemption.discord_id is not None,
            }
            for exemption in guild.member_exemptions.all()
        ],
        "pending": [
            {
                "discord_id": str(row.discord_id),
                "username": row.username or None,
                "display_name": row.display_name or None,
                "reason": row.reason,
                "flagged_at": row.flagged_at,
                "remove_after": row.flagged_at + grace,
            }
            for row in rows
        ],
        "pending_total": guild.member_removals.count(),
    }


def _allowed_user_ids(guild: DiscordGuild, corporation) -> set[int]:
    states = {DiscordRoleMapping.STATE_MEMBER}
    if guild.member_policy == DiscordGuild.MEMBER_POLICY_ALLIANCE:
        states.add(DiscordRoleMapping.STATE_ALLIANCE_MEMBER)
    qualifying = qualifying_user_ids("corporation", corporation, states)
    return set().union(*qualifying.values())


def _top_position(member: dict, positions: dict) -> int:
    return max(
        (positions.get(role_id, 0) for role_id in _role_ids(member["roles"])),
        default=0,
    )


class _Exemptions:
    def __init__(self, guild: DiscordGuild):
        self.rows = list(guild.member_exemptions.all())
        self.by_id = {
            row.discord_id: row for row in self.rows if row.discord_id
        }
        # Once seen, an exemption follows the account, not the name: whoever
        # takes the name next isn't exempt.
        self.by_name = {
            row.username: row for row in self.rows if not row.discord_id
        }

    def match(self, discord_id: int, username: str) -> bool:
        row = self.by_id.get(discord_id) or self.by_name.get(username)
        if row is None:
            return False
        if row.discord_id is None:
            # Seen for the first time: keep them exempt through a rename.
            row.discord_id = discord_id
            row.save(update_fields=["discord_id"])
        return True


def find_unwelcome(
    guild: DiscordGuild,
    corporation,
    members: list,
    roles: list,
    bot_member: dict,
    owner_id: int | None,
) -> tuple[list[dict], int]:
    """(people who don't meet the policy, how many people are on the server).

    Pure apart from reading the site's accounts; no Discord calls.
    """
    by_id = {_role_id(role): role for role in roles}
    positions = {
        role_id: int(role.get("position") or 0)
        for role_id, role in by_id.items()
        if role_id is not None
    }
    bot_top = _top_position(
        {"roles": bot_member.get("roles") or []}, positions
    )
    allowed = _allowed_user_ids(guild, corporation)
    exemptions = _Exemptions(guild)

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
    linked = dict(
        DiscordUser.objects.filter(
            id__in=[discord_id for discord_id, _, _ in people]
        ).values_list("id", "user_id")
    )

    unwelcome = []
    for discord_id, user, member in people:
        username = str(user.get("username") or "").lower()
        if discord_id == owner_id:
            continue
        if exemptions.match(discord_id, username):
            continue
        staff = _held_permissions(guild, roles, member) & STAFF_PERMISSIONS
        if staff or _top_position(member, positions) >= bot_top:
            continue
        user_id = linked.get(discord_id)
        if user_id is not None and user_id in allowed:
            continue
        if user_id is None:
            reason = DiscordGuildRemoval.REASON_UNLINKED
        elif guild.member_policy == DiscordGuild.MEMBER_POLICY_CORPORATION:
            reason = DiscordGuildRemoval.REASON_NOT_CORPORATION
        else:
            reason = DiscordGuildRemoval.REASON_NOT_ALLIANCE
        unwelcome.append(
            {
                "discord_id": discord_id,
                "username": username[:32],
                "display_name": str(
                    member.get("nick") or user.get("global_name") or ""
                )[:100],
                "reason": reason,
            }
        )
    return unwelcome, len(people)


def _sync_pending(guild: DiscordGuild, unwelcome: list[dict], now) -> list:
    """Make the pending list match this pass. Returns its rows."""
    wanted = {row["discord_id"]: row for row in unwelcome}
    guild.member_removals.exclude(discord_id__in=wanted).delete()
    existing = {row.discord_id: row for row in guild.member_removals.all()}
    for discord_id, row in wanted.items():
        current = existing.get(discord_id)
        if current is None:
            existing[discord_id] = DiscordGuildRemoval.objects.create(
                guild=guild, flagged_at=now, **row
            )
            continue
        changed = [
            field
            for field in ("username", "display_name", "reason")
            if getattr(current, field) != row[field]
        ]
        for field in changed:
            setattr(current, field, row[field])
        if changed:
            current.save(update_fields=changed)
    return list(existing.values())


def _brake_limit(people: int) -> int:
    return max(BRAKE_MIN, int(people * BRAKE_SHARE))


def _kick_reason(guild: DiscordGuild, row: DiscordGuildRemoval) -> str:
    who = (
        "corporation"
        if guild.member_policy == DiscordGuild.MEMBER_POLICY_CORPORATION
        else "alliance"
    )
    return f"minmatar.org: {who} members only ({row.get_reason_display()})"


def _kick(client, guild: DiscordGuild, due: list) -> tuple[int, bool]:
    """(how many were removed, whether the bot lost the permission)."""
    removed = 0
    refused = 0
    for row in due:
        try:
            # A 404 (they already left) comes back without raising.
            client.kick_guild_member(
                row.discord_id, reason=_kick_reason(guild, row)
            )
        except requests.HTTPError as error:
            code = discord_error_code(error)
            if code == MISSING_PERMISSIONS:
                # They outrank the bot now; the next pass tries again.
                refused += 1
                if refused >= LOST_AFTER:
                    return removed, True
                continue
            if code in STOP_CODES:
                return removed, True
            logger.warning(
                "Discord member policy for guild %s stopped: %s",
                guild.guild_id,
                error,
            )
            return removed, False
        except (requests.RequestException, RateLimitException) as error:
            logger.warning(
                "Discord member policy for guild %s stopped: %s",
                guild.guild_id,
                error,
            )
            return removed, False
        refused = 0
        row.delete()
        removed += 1
    return removed, False


def _save_pass(guild: DiscordGuild, **fields) -> None:
    for field, value in fields.items():
        setattr(guild, field, value)
    guild.save(update_fields=[*fields, "updated_at"])


def _read_server(guild: DiscordGuild, client):
    """(bot member, roles, owner id, members), or None when Discord can't
    be read. A lost permission is recorded."""
    loaded = _read_roles(client)
    if isinstance(loaded, BaseException) or loaded is None:
        if isinstance(loaded, BaseException) and _permission_lost(loaded):
            _save_pass(guild, can_kick_members=False)
        return None
    bot_member, roles = loaded
    try:
        owner_id = int(client.get_guild().get("owner_id") or 0) or None
        members = _members(client)
    except (requests.RequestException, RateLimitException) as error:
        if _permission_lost(error):
            _save_pass(guild, can_kick_members=False)
        else:
            logger.warning(
                "Discord member policy for guild %s failed: %s",
                guild.guild_id,
                error,
            )
        return None
    if not members:
        # An empty list is a failed read, not an empty server.
        return None
    return bot_member, roles, owner_id, members


def enforce_guild(guild: DiscordGuild) -> int | None:
    """One pass over one server. Returns how many were removed, or None
    when the pass couldn't run."""
    if _protected(guild) or not guild.is_active:
        return None
    if not guild.member_policy:
        guild.member_removals.all().delete()
        return None
    owned = _owner(guild)
    if owned is None or owned[0] != "corporation":
        return None
    corporation = owned[1]
    if not guild.can_kick_members:
        return None

    client = DiscordClient.for_guild(guild.guild_id)
    server = _read_server(guild, client)
    if server is None:
        return None
    bot_member, roles, owner_id, members = server

    now = timezone.now()
    unwelcome, people = find_unwelcome(
        guild, corporation, members, roles, bot_member, owner_id
    )
    pending = _sync_pending(guild, unwelcome, now)
    grace = timedelta(hours=guild.member_grace_hours)
    due = [row for row in pending if row.flagged_at + grace <= now]

    approved_at = guild.members_approved_at
    approved = approved_at is not None and all(
        row.flagged_at <= approved_at for row in due
    )
    if len(due) > _brake_limit(people) and not approved:
        if guild.members_held_at is None:
            logger.warning(
                "Discord guild %s member policy held: %s of %s would go",
                guild.guild_id,
                len(due),
                people,
            )
        _save_pass(
            guild,
            members_held_at=guild.members_held_at or now,
            members_held_count=len(due),
            members_checked_at=now,
            members_last_removed=0,
        )
        return 0

    removed, lost = _kick(client, guild, due)
    _save_pass(
        guild,
        can_kick_members=not lost,
        members_held_at=None,
        members_held_count=0,
        members_approved_at=None,
        members_checked_at=now,
        members_last_removed=removed,
    )
    if removed:
        logger.info(
            "Discord guild %s member policy: removed %s",
            guild.guild_id,
            removed,
        )
    return removed


def enforce_member_policies(guild_pk: int | None = None) -> None:
    """One pass over every server with a member policy, or a single one."""
    queryset = DiscordGuild.objects.filter(
        is_active=True, can_kick_members=True
    ).exclude(member_policy="")
    if guild_pk is not None:
        queryset = DiscordGuild.objects.filter(pk=guild_pk)
    for guild in queryset:
        enforce_guild(guild)
