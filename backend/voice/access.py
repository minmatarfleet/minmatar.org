"""Who may connect to Mumble, and with what rights: every rule lives here.

``voice_record(character_id)`` is the only entry point. It reads standing
access from existing data (affiliation, features, the Capitals tribe) and
fleet-scoped access from stored ``VoiceGrant`` rows, and returns what the
voice service needs at login and on every reconcile.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from django.db.models import Q
from django.utils import timezone

from campaigns.models import (
    CampaignParty,
    CampaignStatus,
    PartyKind,
    PartySide,
)
from eveonline.models import EveCharacter, EveCorporation
from fleets.endpoints.helpers import is_strategic_fc
from groups.helpers.feature_access import can_use_feature
from tribes.models import TribeGroupMembership
from voice import channels
from voice.models import (
    VoiceBan,
    VoiceChannelLease,
    VoiceGrant,
    VoiceIdentity,
)

RECORD_VERSION = 1
CAPITALS_TRIBE_SLUG = "capitals"

REASON_OK = "ok"
REASON_BANNED = "banned"
REASON_NO_ACCESS = "no_access"


@dataclass
class BranchAccess:
    fleet_id: int
    lease_id: int
    groups: list[str] = field(default_factory=list)
    placement: str = channels.MAINLINE
    commander: bool = False
    # Part of this fleet (running it, in it, volunteered), not just standing
    # access as an FC or capital pilot.
    part_of_fleet: bool = False


@dataclass
class VoiceRecord:
    character_id: int
    identity_id: int | None
    display_name: str
    admitted: bool
    banned: bool
    reason: str
    server_groups: list[str]
    branches: dict[str, BranchAccess]
    preferred_branch: int | None
    version: int = RECORD_VERSION

    def to_json(self) -> dict:
        data = asdict(self)
        data["branches"] = {
            key: asdict(value) for key, value in self.branches.items()
        }
        return data


def _character(character_id: int):
    return (
        EveCharacter.objects.filter(character_id=character_id)
        .select_related("user")
        .first()
    )


def display_name(
    character_id: int, fallback: str = "", corporation_id: int | None = None
) -> str:
    """``[TICKER] Character`` when the corporation is known.

    ``corporation_id`` is the guest's corporation from sign-in, used when
    the site has no row for the character.
    """
    character = _character(character_id)
    name = (character.character_name if character else "") or fallback
    if not name:
        name = str(character_id)
    corporation_id = (
        character.corporation_id if character else None
    ) or corporation_id
    ticker = ""
    if corporation_id:
        ticker = (
            EveCorporation.objects.filter(corporation_id=corporation_id)
            .values_list("ticker", flat=True)
            .first()
            or ""
        )
    return f"[{ticker}] {name}" if ticker else name


def is_banned(character_id: int) -> bool:
    return VoiceBan.active().filter(character_id=character_id).exists()


def _in_capitals_tribe(user) -> bool:
    return TribeGroupMembership.objects.filter(
        user=user,
        status=TribeGroupMembership.STATUS_ACTIVE,
        tribe_group__is_active=True,
        tribe_group__tribe__is_active=True,
        tribe_group__tribe__slug=CAPITALS_TRIBE_SLUG,
    ).exists()


def standing_access(user) -> dict[str, bool]:
    """Access that comes from who the pilot is, not from a fleet."""
    if user is None or not user.is_active:
        return {
            "community": False,
            "commander": False,
            "capitals": False,
            "admin": False,
        }
    return {
        "community": can_use_feature(user, "voice.join"),
        "commander": can_use_feature(user, "voice.commander"),
        "capitals": _in_capitals_tribe(user),
        "admin": can_use_feature(user, "voice.admin") or is_strategic_fc(user),
    }


def _active_grants(character_id: int, now):
    return VoiceGrant.objects.filter(character_id=character_id).exclude(
        expires_at__lte=now
    )


def _allied_fleet_ids(leases, *, character_id, corporation_id, alliance_id):
    """Leased fleets whose active campaign lists this pilot as an ally.

    Character, corporation and alliance entries count; faction entries never
    grant access.
    """
    campaign_fleets: dict[int, list[int]] = {}
    for fleet_id, lease in leases.items():
        campaign = lease.fleet.campaign
        if campaign is not None and campaign.status == CampaignStatus.ACTIVE:
            campaign_fleets.setdefault(campaign.id, []).append(fleet_id)
    if not campaign_fleets:
        return set()
    match = Q(kind=PartyKind.CHARACTER, character_id=character_id)
    if corporation_id:
        match |= Q(kind=PartyKind.CORPORATION, corporation_id=corporation_id)
    if alliance_id:
        match |= Q(kind=PartyKind.ALLIANCE, alliance_id=alliance_id)
    allied_campaigns = set(
        CampaignParty.objects.filter(
            match, side=PartySide.ALLY, campaign_id__in=campaign_fleets
        ).values_list("campaign_id", flat=True)
    )
    return {
        fleet_id
        for campaign_id in allied_campaigns
        for fleet_id in campaign_fleets[campaign_id]
    }


def _placement(lease, *, commander: bool, grants: list) -> str:
    """First match wins: Command, Logistics, the FC's wing mapping, Mainline.

    Capitals and FAX go to Mainline too, so placement never reveals them.
    """
    if commander:
        return channels.COMMAND
    if any(grant.logistics for grant in grants):
        return channels.LOGISTICS
    mapping = lease.wing_channels or {}
    for grant in grants:
        if grant.wing_id is None:
            continue
        channel = mapping.get(str(grant.wing_id))
        if channel in channels.BRANCH_SUBCHANNELS:
            return channel
    return channels.MAINLINE


def voice_record(character_id: int, *, now=None) -> VoiceRecord:
    now = now or timezone.now()
    character_id = int(character_id)
    identity = VoiceIdentity.objects.filter(character_id=character_id).first()
    character = _character(character_id)
    name = display_name(
        character_id,
        identity.character_name if identity else "",
        identity.corporation_id if identity else None,
    )

    if is_banned(character_id):
        return VoiceRecord(
            character_id=character_id,
            identity_id=identity.id if identity else None,
            display_name=name,
            admitted=False,
            banned=True,
            reason=REASON_BANNED,
            server_groups=[],
            branches={},
            preferred_branch=None,
        )

    standing = standing_access(character.user if character else None)
    leases = {
        lease.fleet_id: lease
        for lease in VoiceChannelLease.active()
        .select_related("fleet__campaign")
        .order_by("branch")
    }

    allied_fleets = _allied_fleet_ids(
        leases,
        character_id=character_id,
        corporation_id=(
            (character.corporation_id if character else None)
            or (identity.corporation_id if identity else None)
        ),
        alliance_id=(
            (character.alliance_id if character else None)
            or (identity.alliance_id if identity else None)
        ),
    )

    grants_by_fleet: dict[int, list] = {}
    for grant in _active_grants(character_id, now):
        if grant.fleet_id in leases:
            grants_by_fleet.setdefault(grant.fleet_id, []).append(grant)

    branches: dict[str, BranchAccess] = {}
    for fleet_id, lease in leases.items():
        grants = grants_by_fleet.get(fleet_id, [])
        allied = fleet_id in allied_fleets
        if not (
            grants or allied or standing["commander"] or standing["capitals"]
        ):
            continue
        roles = {grant.role for grant in grants}
        commander = standing["commander"] or VoiceGrant.ROLE_COMMANDER in roles
        capitals = (
            commander
            or standing["capitals"]
            or VoiceGrant.ROLE_CAPITAL in roles
        )
        groups = [channels.GROUP_FLEET]
        if commander:
            groups.append(channels.GROUP_COMMANDERS)
        if capitals:
            groups.append(channels.GROUP_CAPITALS)
        branches[str(lease.branch)] = BranchAccess(
            fleet_id=fleet_id,
            lease_id=lease.id,
            groups=groups,
            placement=_placement(lease, commander=commander, grants=grants),
            commander=commander,
            part_of_fleet=any(
                grant.source in VoiceGrant.PART_OF_FLEET for grant in grants
            ),
        )

    server_groups = []
    if standing["community"]:
        server_groups.append(channels.GROUP_COMMUNITY)
    if standing["admin"]:
        server_groups.append(channels.GROUP_VOICEADMIN)

    admitted = bool(standing["community"] or branches)
    return VoiceRecord(
        character_id=character_id,
        identity_id=identity.id if identity else None,
        display_name=name,
        admitted=admitted,
        banned=False,
        reason=REASON_OK if admitted else REASON_NO_ACCESS,
        server_groups=server_groups,
        branches=branches,
        preferred_branch=_preferred_branch(branches, len(leases)),
    )


def _preferred_branch(branches: dict[str, BranchAccess], lease_count: int):
    """Which fleet placement uses when the pilot may enter several.

    A fleet they're part of wins; otherwise the only active Mumble fleet;
    otherwise none, and they pick.
    """
    part_of = sorted(
        int(key) for key, b in branches.items() if b.part_of_fleet
    )
    if part_of:
        return part_of[0]
    if lease_count == 1 and len(branches) == 1:
        return int(next(iter(branches)))
    return None
