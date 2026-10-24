"""Public aggregate facts for a corporation's About page.

Counts are corporation-wide. No character or user names are included.
Community status is current. Fleets, ships, and kills use ACTIVITY_DAYS.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta

from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.helpers.corporations.kills import ACTIVITY_DAYS, RecentKills
from eveonline.helpers.corporations.timezones import (
    observed_prime_buckets_for_users,
)
from eveonline.killmail_classes import (
    CAPSULE_TYPE_IDS,
    SMALL_GANG_MAX_ATTACKERS,
    SOLO_MAX_ATTACKERS,
)
from eveonline.models import EveCharacter
from feed.constants import CAPITAL_SHIP_GROUPS
from feed.helpers.eve_names import CAPSULE_GROUP_NAME
from fleets.models import (
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
)
from groups.models import UserCommunityStatus
from surveys.constants import (
    ACTIVITY_CORE,
    ACTIVITY_INACTIVE,
    ACTIVITY_LAPSING,
    ACTIVITY_REGULAR,
    activity_tier,
)

# The surveys activity tiers: distinct fleets in a trailing quarter.
TIER_INACTIVE = ACTIVITY_INACTIVE
TIER_LAPSING = ACTIVITY_LAPSING
TIER_REGULAR = ACTIVITY_REGULAR
TIER_CORE = ACTIVITY_CORE

# Attacker buckets from eveonline.killmail_classes, shared with alliance
# health. The 11+ signal is "kill" there.
KILL_SOLO = "solo"
KILL_SMALL_GANG = "small_gang"
KILL_FLEET = "fleet"

SHIP_DPS = "dps"
SHIP_LOGISTICS = "logistics"
SHIP_SUPPORT = "support"
SHIP_CAPITAL = "capital"

# feed.constants.CAPITAL_SHIP_GROUPS plus fleet-composition capital names.
# Industrial hulls and anything outside these roles are left off the public mix.
CAPITAL_GROUPS = CAPITAL_SHIP_GROUPS | frozenset(
    {
        "Lancer Dreadnought",
        "Capital",
        "Super Capital",
        "Super Carrier",
        "Command Carrier",
    }
)
LOGISTICS_GROUPS = frozenset(
    {
        "Logistics",
        "Logistics Frigate",
        "Logistics Cruiser",
        "Logistics Crusiers",
    }
)
# Ewar, tackle, command, and recon. SRP folds these into "support".
SUPPORT_GROUPS = frozenset(
    {
        "Electronic Attack Ship",
        "Covert Ops",
        "Interceptor",
        "Interdictor",
        "Command Destroyer",
        "Heavy Interdiction Cruiser",
        "Recon Ship",
        "Force Recon Ship",
        "Combat Recon Ship",
        "Command Ship",
    }
)
INDUSTRIAL_GROUPS = frozenset(
    {
        "Mining Frigate",
        "Expedition Frigate",
        "Mining Barge",
        "Industrial",
        "Transport Ship",
        "Freighter",
        "Jump Freighter",
        "Jump Freighters",
        "Industrial Command Ship",
        "Capital Industrial Ship",
    }
)
DPS_GROUPS = frozenset(
    {
        "Frigate",
        "Assault Frigate",
        "Destroyer",
        "Tactical Destroyer",
        "Cruiser",
        "Heavy Assault Cruiser",
        "Strategic Cruiser",
        "Battlecruiser",
        "Combat Battlecruiser",
        "Attack Battlecruiser",
        "Battleship",
        "Marauder",
        "Black Ops",
        "Stealth Bomber",
    }
)
SKIP_GROUPS = frozenset({CAPSULE_GROUP_NAME, "Shuttle"})
# T1 hulls whose EVE group is plain Frigate/Cruiser but whose fleet role is not.
T1_LOGISTICS_TYPE_IDS = frozenset(
    {
        625,  # Augoror
        634,  # Exequror
        620,  # Osprey
        631,  # Scythe
        582,  # Bantam
        592,  # Navitas
        599,  # Burst
        590,  # Inquisitor
    }
)
T1_EWAR_TYPE_IDS = frozenset(
    {
        584,  # Griffin
        609,  # Maulus
        3766,  # Vigil
        2161,  # Crucifier
        632,  # Blackbird
        633,  # Celestis
        628,  # Arbitrator
        630,  # Bellicose
    }
)

COMMUNITY_ORDER = (
    UserCommunityStatus.STATUS_ACTIVE,
    UserCommunityStatus.STATUS_TRIAL,
    UserCommunityStatus.STATUS_ON_LEAVE,
)
FLEET_ORDER = (TIER_INACTIVE, TIER_LAPSING, TIER_REGULAR, TIER_CORE)
SHIP_ORDER = (
    SHIP_DPS,
    SHIP_LOGISTICS,
    SHIP_SUPPORT,
    SHIP_CAPITAL,
)
KILL_ORDER = (KILL_SOLO, KILL_SMALL_GANG, KILL_FLEET)


def corporation_public_summary(
    corporation, kills: RecentKills | None = None
) -> dict:
    """Aggregate community, fleet, ship, and kill facts for one corporation.

    Pass `kills` preloaded for many corporations to avoid reloading
    recent killmails per corporation.
    """
    cutoff = timezone.now() - timedelta(days=ACTIVITY_DAYS)
    character_ids, user_ids, char_to_user = _corp_characters(corporation)
    if kills is None:
        kills = RecentKills(character_ids)
    fleet_instances, fleet_counts, ship_counts, pilot_fleets = _fleet_facts(
        character_ids, user_ids, char_to_user, cutoff
    )
    killmails, kill_counts = _kill_facts(character_ids, kills)
    return {
        "window_days": ACTIVITY_DAYS,
        "community": {
            "humans": len(user_ids),
            "slices": _slices(COMMUNITY_ORDER, _community_counts(user_ids)),
        },
        "fleet_participation": {
            "fleet_instances": fleet_instances,
            "humans": len(user_ids),
            "slices": _slices(FLEET_ORDER, fleet_counts),
        },
        "fleet_ships": {
            "pilot_fleets": pilot_fleets,
            "slices": [
                {"key": key, "count": round(ship_counts[key], 2)}
                for key in SHIP_ORDER
                if ship_counts[key]
            ],
        },
        "kills": {
            "killmails": killmails,
            "slices": _slices(KILL_ORDER, kill_counts),
        },
    }


def fleet_tier(fleet_count: int) -> str:
    return activity_tier(fleet_count)


def kill_bucket(attacker_count: int) -> str:
    if attacker_count <= SOLO_MAX_ATTACKERS:
        return KILL_SOLO
    if attacker_count <= SMALL_GANG_MAX_ATTACKERS:
        return KILL_SMALL_GANG
    return KILL_FLEET


def ship_bucket(
    group_name: str | None, type_id: int | None = None
) -> str | None:
    if type_id in T1_LOGISTICS_TYPE_IDS:
        return SHIP_LOGISTICS
    if type_id in T1_EWAR_TYPE_IDS:
        return SHIP_SUPPORT
    name = group_name or ""
    if name in SKIP_GROUPS:
        return None
    if name in CAPITAL_GROUPS:
        return SHIP_CAPITAL
    if name in LOGISTICS_GROUPS:
        return SHIP_LOGISTICS
    if name in SUPPORT_GROUPS:
        return SHIP_SUPPORT
    if name in INDUSTRIAL_GROUPS:
        return None
    if name in DPS_GROUPS:
        return SHIP_DPS
    return None


def _corp_characters(corporation):
    rows = EveCharacter.objects.filter(
        corporation_id=corporation.corporation_id
    ).values_list("character_id", "user_id")
    character_ids = []
    user_ids = set()
    char_to_user = {}
    for character_id, user_id in rows:
        character_ids.append(character_id)
        if user_id:
            user_ids.add(user_id)
            char_to_user[character_id] = user_id
    return character_ids, user_ids, char_to_user


def _community_counts(user_ids: set[int]) -> Counter:
    """Explicit community status only, one row per linked user.

    Pilots with no UserCommunityStatus row are left out of the blend.
    The human total still includes them so the page can say how many
    have no status on file.
    """
    counts: Counter = Counter()
    if not user_ids:
        return counts
    statuses = UserCommunityStatus.objects.filter(
        user_id__in=user_ids
    ).values_list("status", flat=True)
    for status in statuses:
        if status in COMMUNITY_ORDER:
            counts[status] += 1
    return counts


def _fleet_facts(character_ids, user_ids, char_to_user, cutoff):
    fleets_by_user = {user_id: set() for user_id in user_ids}
    instances = set()
    if not character_ids:
        return 0, Counter(fleet_tier(0) for _ in user_ids), Counter(), 0

    member_rows = list(
        EveFleetInstanceMember.objects.filter(
            character_id__in=character_ids,
            join_time__gte=cutoff,
        ).values_list(
            "id",
            "character_id",
            "eve_fleet_instance_id",
            "ship_type_id",
        )
    )
    ships_by_member = _snapshot_ships([row[0] for row in member_rows])
    hulls_by_pilot_fleet = defaultdict(list)
    for member_id, character_id, instance_id, ship_type_id in member_rows:
        instances.add(instance_id)
        user_id = char_to_user.get(character_id)
        if user_id in fleets_by_user:
            fleets_by_user[user_id].add(instance_id)
        # Alts fold into their owner; unlinked characters stand alone.
        pilot = ("user", user_id) if user_id else ("character", character_id)
        hulls_by_pilot_fleet[(pilot, instance_id)].extend(
            _attendance_ships(ship_type_id, ships_by_member.get(member_id))
        )
    ship_counts, pilot_fleets = _ship_roles(hulls_by_pilot_fleet)
    observed = observed_prime_buckets_for_users(list(user_ids))
    tier_counts: Counter = Counter()
    for user_id, fleet_ids in fleets_by_user.items():
        if not observed.get(user_id):
            tier_counts[TIER_INACTIVE] += 1
            continue
        tier_counts[fleet_tier(len(fleet_ids))] += 1
    return len(instances), tier_counts, ship_counts, pilot_fleets


def _snapshot_ships(member_ids: list[int]) -> dict[int, set[int]]:
    ships = defaultdict(set)
    if not member_ids:
        return ships
    rows = EveFleetInstanceMemberShipSnapshot.objects.filter(
        member_id__in=member_ids
    ).values_list("member_id", "ship_type_id")
    for member_id, ship_type_id in rows:
        if ship_type_id:
            ships[member_id].add(int(ship_type_id))
    return ships


def _attendance_ships(member_ship, snapshot_ids: set[int] | None) -> list[int]:
    """Hulls brought to one fleet attendance, ignoring capsules.

    Snapshots win when they contain a real hull, so an end-of-fleet pod
    does not replace the ship they flew.
    """
    flown = [
        ship_id
        for ship_id in (snapshot_ids or set())
        if ship_id and ship_id not in CAPSULE_TYPE_IDS
    ]
    if flown:
        return flown
    if member_ship and int(member_ship) not in CAPSULE_TYPE_IDS:
        return [int(member_ship)]
    return []


def _ship_roles(hulls_by_pilot_fleet: dict) -> tuple[Counter, int]:
    """Role mix with one vote per person per fleet.

    The vote is split evenly across the roles that person fielded, so a
    DPS main with a logistics alt adds half to each. Reshipping into the
    same role does not count twice. Shares always sum to 100%.
    """
    counts: Counter = Counter()
    type_ids = {
        type_id for hulls in hulls_by_pilot_fleet.values() for type_id in hulls
    }
    if not type_ids:
        return counts, 0
    groups = {
        type_id: group_name or ""
        for type_id, group_name in EveType.objects.filter(
            id__in=type_ids
        ).values_list("id", "eve_group__name")
    }
    pilot_fleets = 0
    for hulls in hulls_by_pilot_fleet.values():
        roles = {
            ship_bucket(groups.get(type_id, ""), type_id) for type_id in hulls
        }
        roles.discard(None)
        if not roles:
            continue
        pilot_fleets += 1
        for role in roles:
            counts[role] += 1 / len(roles)
    return counts, pilot_fleets


def _kill_facts(character_ids, kills: RecentKills):
    counts: Counter = Counter()
    killmail_ids = kills.killmails_for(character_ids)
    for attackers in kills.attacker_counts(killmail_ids).values():
        counts[kill_bucket(attackers)] += 1
    return sum(counts.values()), counts


def _slices(order: tuple[str, ...], counts: Counter) -> list[dict]:
    return [
        {"key": key, "count": int(counts[key])} for key in order if counts[key]
    ]
