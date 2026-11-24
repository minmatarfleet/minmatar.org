"""Campaign roles: Coordinator, FC, Diplomat, Recon and IT.

Each role mirrors a role on the campaign's coordination Discord server.
Discord decides who holds it: ``sync`` reads the server's members and
rewrites the campaign's rosters to match. A role holder sees the campaign
even while it is undisclosed, reads the parts their roles cover and edits
the parts their roles own.

Adding someone by character on the site makes a pending ``site`` row. Once
that character's owner has linked Discord and joined the server, the sync
gives them the Discord role, and from then on Discord is in charge of it.
Removing someone on the site takes the Discord role away too, or the next
sync would bring them back.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from campaigns.models import (
    Campaign,
    CampaignRole,
    CampaignRoleKind,
    CampaignRoleMember,
)

logger = logging.getLogger(__name__)

KINDS = [kind.value for kind in CampaignRoleKind]

# What each role reads on an undisclosed campaign (the coordinator scopes).
READS: dict[str, set[str]] = {
    CampaignRoleKind.COORDINATOR: {
        "sides",
        "structures",
        "timers",
        "fleets",
        "fittings",
    },
    CampaignRoleKind.FC: {"structures", "timers", "fleets", "fittings"},
    CampaignRoleKind.DIPLOMAT: {"sides"},
    CampaignRoleKind.RECON: {"structures", "timers"},
    # IT connects a server; it reads nothing of the plan.
    CampaignRoleKind.IT: set(),
}

# What each role edits. ``roles`` is adding and removing role holders;
# ``discord`` is adding the bot to their own server and picking its
# channels. Settings, disclosure, the order and the theater stay with
# managers.
EDITS: dict[str, set[str]] = {
    CampaignRoleKind.COORDINATOR: {
        "sides",
        "structures",
        "timers",
        "roles",
        "discord",
    },
    CampaignRoleKind.FC: {"fleets"},
    CampaignRoleKind.DIPLOMAT: {"sides"},
    CampaignRoleKind.RECON: {"structures", "timers"},
    CampaignRoleKind.IT: {"discord"},
}

# Discord role names matched on the first sync, lower case.
NAMES: dict[str, tuple[str, ...]] = {
    CampaignRoleKind.COORDINATOR: ("coordinator", "coordinators"),
    CampaignRoleKind.FC: ("fc", "fcs", "fleet commander"),
    CampaignRoleKind.DIPLOMAT: ("diplomat", "diplomats"),
    CampaignRoleKind.RECON: ("recon", "scout", "scouts"),
    CampaignRoleKind.IT: ("it", "tech", "tech support"),
}


class RoleError(Exception):
    """Something the caller should show: no such character, no server."""


def ensure_roles(campaign: Campaign) -> list[CampaignRole]:
    existing = {role.kind: role for role in campaign.roles.all()}
    for kind in KINDS:
        if kind not in existing:
            existing[kind] = CampaignRole.objects.get_or_create(
                campaign=campaign, kind=kind
            )[0]
    return [existing[kind] for kind in KINDS]


def _user(user):
    return user if getattr(user, "is_authenticated", False) else None


def _member_q(user):
    # pylint: disable=import-outside-toplevel
    from django.db.models import Q

    from eveonline.models import EveCharacter

    character_ids = list(
        EveCharacter.objects.filter(user=user).values_list(
            "character_id", flat=True
        )
    )
    discord_id = getattr(getattr(user, "discord_user", None), "id", None)
    # Pending site rows count once the character is the user's: the
    # campaign side is already decided, only Discord is behind.
    query = Q(user=user) | Q(character_id__in=character_ids)
    if discord_id:
        query |= Q(discord_user_id=discord_id)
    return query


def kinds_for(user, campaign: Campaign) -> set[str]:
    """The roles ``user`` holds on ``campaign``."""
    user = _user(user)
    if user is None:
        return set()
    return set(
        CampaignRoleMember.objects.filter(role__campaign=campaign)
        .filter(_member_q(user))
        .values_list("role__kind", flat=True)
    )


def campaign_ids(user) -> set[int]:
    """Campaigns ``user`` holds any role on."""
    user = _user(user)
    if user is None:
        return set()
    return set(
        CampaignRoleMember.objects.filter(_member_q(user)).values_list(
            "role__campaign_id", flat=True
        )
    )


def reads(user, campaign: Campaign) -> set[str]:
    found: set[str] = set()
    for kind in kinds_for(user, campaign):
        found |= READS.get(kind, set())
    return found


def may_edit(user, campaign: Campaign, area: str) -> bool:
    return any(
        area in EDITS.get(kind, set()) for kind in kinds_for(user, campaign)
    )


# Discord ---------------------------------------------------------------


def _client(campaign: Campaign):
    # pylint: disable=import-outside-toplevel
    from campaigns.services.coordination import guild_id
    from discord.client import DiscordClient

    server = guild_id(campaign)
    if not server:
        raise RoleError("This campaign has no coordination Discord server.")
    return DiscordClient(guild_id=server)


def discord_roles(campaign: Campaign) -> list[dict]:
    """The coordination server's roles, for the picker. Empty on failure."""
    try:
        rows = _client(campaign).get_roles()
    except Exception:  # pylint: disable=broad-except
        logger.warning("Campaign %s: could not list roles", campaign.id)
        return []
    return [
        {"id": str(row["id"]), "name": row.get("name", "")}
        for row in sorted(rows, key=lambda r: -int(r.get("position", 0)))
        if row.get("name") != "@everyone" and not row.get("managed")
    ]


def _match_names(roles: list[CampaignRole], server_roles: list[dict]):
    by_name = {
        str(row.get("name", "")).strip().lower(): row for row in server_roles
    }
    for role in roles:
        if role.discord_role_id:
            continue
        for name in NAMES[role.kind]:
            row = by_name.get(name)
            if row:
                role.discord_role_id = int(row["id"])
                role.discord_role_name = row.get("name", "")
                role.save(
                    update_fields=["discord_role_id", "discord_role_name"]
                )
                break


def _display_name(member: dict) -> str:
    user = member.get("user") or {}
    return (
        member.get("nick")
        or user.get("global_name")
        or user.get("username")
        or ""
    )


def _profiles(discord_ids: set[int]) -> dict[int, dict]:
    """Site user and main character for each linked Discord account."""
    # pylint: disable=import-outside-toplevel
    from campaigns.services.coordinators import _names
    from discord.models import DiscordUser
    from eveonline.models import EvePlayer

    linked = DiscordUser.objects.filter(id__in=discord_ids).select_related(
        "user"
    )
    players = {
        player.user_id: player
        for player in EvePlayer.objects.filter(
            user_id__in=[row.user_id for row in linked]
        ).select_related("primary_character")
    }
    out = {}
    for row in linked:
        player = players.get(row.user_id)
        character = player.primary_character if player else None
        corporation = alliance = ""
        if character is not None:
            corporation, alliance = _names(
                character.corporation_id, character.alliance_id
            )
        out[row.id] = {
            "user": row.user,
            "character_id": character.character_id if character else None,
            "character_name": character.character_name if character else "",
            "corporation_name": corporation,
            "alliance_name": alliance,
        }
    return out


def _discord_id_for(user) -> int | None:
    return getattr(getattr(user, "discord_user", None), "id", None)


def _owner(character_id: int | None):
    # pylint: disable=import-outside-toplevel
    from eveonline.models import EveCharacter

    if not character_id:
        return None
    character = (
        EveCharacter.objects.filter(
            character_id=character_id, user__isnull=False
        )
        .select_related("user")
        .first()
    )
    return character.user if character else None


def sync(campaign: Campaign) -> dict:
    """Make the campaign's rosters match the coordination server.

    Pending site rows whose owner is on the server get the Discord role
    first, so they survive. Returns counts per role.
    """
    roles = ensure_roles(campaign)
    client = _client(campaign)
    if campaign.coordination_guild_id:
        # Only on a server of its own: on ours, "FC" is every alliance FC.
        _match_names(roles, client.get_roles())
    members = client.get_members()
    on_server = {int(m["user"]["id"]): m for m in members if m.get("user")}
    granted = _grant_pending(client, roles, on_server)

    holders: dict[int, set[int]] = {}
    for discord_id, member in on_server.items():
        for role_id in member.get("roles") or []:
            holders.setdefault(int(role_id), set()).add(discord_id)
    for role_id, discord_ids in granted.items():
        holders.setdefault(role_id, set()).update(discord_ids)
    profiles = _profiles(set(on_server))

    counts = {}
    now = timezone.now()
    for role in roles:
        if not role.discord_role_id:
            role.sync_error = "No Discord role picked"
            role.save(update_fields=["sync_error"])
            counts[role.kind] = None
            continue
        wanted = holders.get(role.discord_role_id, set())
        with transaction.atomic():
            role.members.filter(
                source=CampaignRoleMember.Source.DISCORD
            ).exclude(discord_user_id__in=wanted).delete()
            for discord_id in wanted:
                profile = profiles.get(discord_id, {})
                defaults = {
                    "source": CampaignRoleMember.Source.DISCORD,
                    "discord_name": _display_name(on_server[discord_id]),
                    "user": profile.get("user"),
                }
                # Someone not linked keeps the character they were invited
                # as (``add`` from a suggestion) until they link Discord.
                if profile.get("character_id"):
                    defaults.update(
                        {
                            key: profile.get(key) or ""
                            for key in (
                                "character_name",
                                "corporation_name",
                                "alliance_name",
                            )
                        }
                    )
                    defaults["character_id"] = profile["character_id"]
                CampaignRoleMember.objects.update_or_create(
                    role=role, discord_user_id=discord_id, defaults=defaults
                )
            # A pending row whose owner now holds the role is that row.
            role.members.filter(
                source=CampaignRoleMember.Source.SITE,
                user__discord_user__id__in=wanted,
            ).delete()
            role.synced_at = now
            role.sync_error = ""
            role.save(update_fields=["synced_at", "sync_error"])
        counts[role.kind] = len(wanted)
    # pylint: disable-next=import-outside-toplevel
    from campaigns.services import role_suggestions

    role_suggestions.warm(campaign)
    logger.info("Campaign %s roles synced: %s", campaign.id, counts)
    return counts


def _grant_pending(client, roles, on_server) -> dict[int, set[int]]:
    """Give the Discord role to pending site rows whose owner has linked
    Discord and is on the server."""
    granted: dict[int, set[int]] = {}
    for role in roles:
        if not role.discord_role_id:
            continue
        for row in role.members.filter(source=CampaignRoleMember.Source.SITE):
            user = row.user or _owner(row.character_id)
            discord_id = _discord_id_for(user)
            if not discord_id or discord_id not in on_server:
                continue
            if row.user_id is None:
                row.user = user
                row.save(update_fields=["user"])
            try:
                client.add_user_role(discord_id, role.discord_role_id)
            except Exception:  # pylint: disable=broad-except
                logger.warning(
                    "Campaign %s: could not give %s role %s",
                    role.campaign_id,
                    discord_id,
                    role.discord_role_id,
                )
                continue
            granted.setdefault(role.discord_role_id, set()).add(discord_id)
    return granted


def _role(campaign: Campaign, kind: str) -> CampaignRole:
    if kind not in KINDS:
        raise RoleError("Unknown role.")
    return next(r for r in ensure_roles(campaign) if r.kind == kind)


def _lookup(name: str) -> dict:
    # pylint: disable-next=import-outside-toplevel
    from campaigns.services import coordinators

    try:
        return coordinators.lookup(name)
    except coordinators.NotFound as error:
        raise RoleError("No character has that exact name.") from error


def add_character(
    campaign: Campaign, kind: str, name: str, by
) -> CampaignRoleMember:
    """Add a role holder by character name (pending until Discord)."""
    role = _role(campaign, kind)
    found = _lookup(name)
    member = CampaignRoleMember.objects.update_or_create(
        role=role,
        character_id=found["character_id"],
        source=CampaignRoleMember.Source.SITE,
        defaults={
            "character_name": found["character_name"],
            "corporation_name": found["corporation_name"],
            "alliance_name": found["alliance_name"],
            "user": _owner(found["character_id"]),
            "added_by": by,
        },
    )[0]
    notify(member)
    return member


def add_discord_member(
    campaign: Campaign,
    kind: str,
    discord_user_id: int,
    by,
    character_name: str = "",
) -> CampaignRoleMember:
    """Invite someone already on the coordination server, as the character
    picked for them (the suggested one unless ``character_name`` says
    otherwise).

    With the role pointed at a Discord role they get it there at once and
    the row is a ``discord`` one, kept by every sync. Without one the row
    waits like a character invite, tied to their Discord account too.
    """
    # pylint: disable-next=import-outside-toplevel
    from campaigns.services import role_suggestions

    role = _role(campaign, kind)
    suggestion = role_suggestions.find(campaign, discord_user_id)
    if suggestion is None:
        raise RoleError("They are not on the coordination server.")
    if character_name:
        found = _lookup(character_name)
    elif role_suggestions.trusted(suggestion):
        found = {
            key: suggestion[key]
            for key in (
                "character_id",
                "character_name",
                "corporation_name",
                "alliance_name",
            )
        }
    else:
        raise RoleError("Pick the character they fly.")
    owner = _owner(found["character_id"])
    fields = {
        "discord_name": suggestion["discord_name"],
        "character_id": found["character_id"],
        "character_name": found["character_name"],
        "corporation_name": found["corporation_name"],
        "alliance_name": found["alliance_name"],
        "user": owner,
        "added_by": by,
    }
    if role.discord_role_id:
        try:
            _client(campaign).add_user_role(
                discord_user_id, role.discord_role_id
            )
        except Exception as error:  # pylint: disable=broad-except
            raise RoleError(
                "Discord would not give them the role. Check the bot can "
                "manage roles on the server."
            ) from error
        fields["source"] = CampaignRoleMember.Source.DISCORD
    else:
        fields["source"] = CampaignRoleMember.Source.SITE
    # A pending invite for the same character is this one now.
    role.members.filter(
        source=CampaignRoleMember.Source.SITE,
        character_id=found["character_id"],
    ).exclude(discord_user_id=discord_user_id).delete()
    member = CampaignRoleMember.objects.update_or_create(
        role=role, discord_user_id=discord_user_id, defaults=fields
    )[0]
    notify(member)
    return member


def notify(member: CampaignRoleMember) -> bool:
    """DM the character's owner that they hold the role. Nobody to tell
    until someone on the site owns the character."""
    # pylint: disable=import-outside-toplevel
    from campaigns.services.coordinators import _inviter_name
    from campaigns.services.discord_posts import (
        POSTING_STATUSES,
        campaign_url,
    )
    from notifications.service import notify_user
    from notifications.types.campaigns import (
        CAMPAIGN_COORDINATOR_INVITED_KEY,
    )

    campaign = member.role.campaign
    user = member.user or _owner(member.character_id)
    if user is None or campaign.status not in POSTING_STATUSES:
        return False
    notify_user(
        user,
        CAMPAIGN_COORDINATOR_INVITED_KEY,
        {
            "campaign_name": campaign.name,
            "character_name": member.character_name,
            "inviter": _inviter_name(member.added_by),
            "url": campaign_url(campaign),
            "role": member.role.kind,
        },
        idempotency_key=(
            f"{CAMPAIGN_COORDINATOR_INVITED_KEY}:role:{member.role_id}:"
            f"{member.character_id}"
        ),
    )
    return True


def remove_member(member: CampaignRoleMember) -> None:
    """Drop a role holder here and on Discord."""
    role = member.role
    if member.discord_user_id and role.discord_role_id:
        try:
            _client(role.campaign).remove_user_role(
                member.discord_user_id, role.discord_role_id
            )
        except Exception as error:  # pylint: disable=broad-except
            raise RoleError(
                "Discord would not take the role away. Remove it there."
            ) from error
    member.delete()


def set_discord_role(role: CampaignRole, discord_role_id: int | None) -> None:
    name = ""
    if discord_role_id:
        known = {
            int(row["id"]): row["name"] for row in discord_roles(role.campaign)
        }
        if discord_role_id not in known:
            raise RoleError("That role is not on the coordination server.")
        name = known[discord_role_id]
    role.discord_role_id = discord_role_id
    role.discord_role_name = name
    role.save(update_fields=["discord_role_id", "discord_role_name"])
    # The old role's holders are no longer this role's.
    role.members.filter(source=CampaignRoleMember.Source.DISCORD).delete()
