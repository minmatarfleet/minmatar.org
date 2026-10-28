"""One pilot's trial picture: trial length, tiers, ships brought, kills.

The tiers, trial day and pace come from the latest health snapshot
(alliance.helpers.trial_peers). Ships and kills are read live for one
person's characters, which stays cheap: every query is keyed by their
character ids.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any, Optional

from django.db.models import Count
from django.utils import timezone

from alliance.helpers.hygiene import MIN_APPROVE_DAYS
from alliance.helpers.trial_peers import (
    ON_PACE_DECISIONS,
    compare_user,
    corp_trial_length,
    trial_row,
)
from alliance.models import AllianceHealthSnapshot
from applications.l3arn import is_academy
from eveonline.killmail_classes import (
    SMALL_GANG_MAX_ATTACKERS,
    SOLO_MAX_ATTACKERS,
)
from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
)
from fittings.models import ACADEMY_ROLE, EveDoctrineFitting
from fleets.models import EveFleetInstanceMember
from groups.models import UserCommunityStatus

WINDOW_DAYS = 90
TRIAL_SCALE_DAYS = 90
OFF_DOCTRINE = "off_doctrine"
# Best first: a pilot whose alts brought two hulls to one fleet is counted
# by the more useful one.
ROLE_ORDER = ("primary", "support", "utility", ACADEMY_ROLE, OFF_DOCTRINE)
RECENT_FLEETS = 10


def latest_payload() -> Optional[dict]:
    snapshot = (
        AllianceHealthSnapshot.objects.order_by("-computed_at")
        .only("payload")
        .first()
    )
    return snapshot.payload if snapshot else None


def helpful_role(role: Optional[str], academy: bool) -> bool:
    """Primary, support and utility help a fleet; Academy fits only from
    Academy pilots; off-doctrine hulls never."""
    if role in ("primary", "support", "utility"):
        return True
    return role == ACADEMY_ROLE and academy


def fleet_ships(character_ids: list[int], days: int = WINDOW_DAYS) -> list:
    """One row per fleet the person was in: the hull and its doctrine role.

    Role is None when the fleet had no doctrine.
    """
    cutoff = timezone.now() - timedelta(days=days)
    rows = list(
        EveFleetInstanceMember.objects.filter(
            character_id__in=character_ids, join_time__gte=cutoff
        ).values(
            "eve_fleet_instance_id",
            "join_time",
            "ship_type_id",
            "ship_name",
            "eve_fleet_instance__eve_fleet_id",
            "eve_fleet_instance__eve_fleet__start_time",
            "eve_fleet_instance__eve_fleet__doctrine_id",
            "eve_fleet_instance__eve_fleet__doctrine__name",
        )
    )
    doctrine_ids = {
        row["eve_fleet_instance__eve_fleet__doctrine_id"]
        for row in rows
        if row["eve_fleet_instance__eve_fleet__doctrine_id"]
    }
    roles: dict[tuple[int, int], set[str]] = defaultdict(set)
    for doctrine_id, role, ship_id in EveDoctrineFitting.objects.filter(
        doctrine_id__in=doctrine_ids
    ).values_list("doctrine_id", "role", "fitting__ship_id"):
        roles[(doctrine_id, ship_id)].add(role)

    def role_for(doctrine_id, ship_type_id) -> Optional[str]:
        if not doctrine_id:
            return None
        found = roles.get((doctrine_id, ship_type_id))
        if not found:
            return OFF_DOCTRINE
        return min(found, key=_role_rank)

    by_fleet: dict[int, dict] = {}
    for row in rows:
        doctrine_id = row["eve_fleet_instance__eve_fleet__doctrine_id"]
        entry = {
            "fleet_id": row["eve_fleet_instance__eve_fleet_id"],
            "start_time": row["eve_fleet_instance__eve_fleet__start_time"]
            or row["join_time"],
            "doctrine_name": row[
                "eve_fleet_instance__eve_fleet__doctrine__name"
            ],
            "ship_type_id": row["ship_type_id"],
            "ship_name": row["ship_name"],
            "role": role_for(doctrine_id, row["ship_type_id"]),
        }
        key = row["eve_fleet_instance_id"]
        kept = by_fleet.get(key)
        if kept is None or _role_rank(entry["role"]) < _role_rank(
            kept["role"]
        ):
            by_fleet[key] = entry
    return sorted(
        by_fleet.values(), key=lambda entry: entry["start_time"], reverse=True
    )


def _role_rank(role: Optional[str]) -> int:
    if role in ROLE_ORDER:
        return ROLE_ORDER.index(role)
    return len(ROLE_ORDER)


def ships_summary(fleets: list[dict], academy: bool) -> dict[str, Any]:
    """Doctrine fleets counted, how many in a helpful hull, and per hull/role."""
    doctrine_fleets = [fleet for fleet in fleets if fleet["role"]]
    counts = Counter(
        (fleet["ship_type_id"], fleet["ship_name"], fleet["role"])
        for fleet in doctrine_fleets
    )
    hulls = [
        {
            "ship_type_id": ship_type_id,
            "ship_name": ship_name,
            "role": role,
            "count": count,
            "helpful": helpful_role(role, academy),
        }
        for (ship_type_id, ship_name, role), count in counts.most_common()
    ]
    return {
        "doctrine_fleets": len(doctrine_fleets),
        "helpful_fleets": sum(
            1
            for fleet in doctrine_fleets
            if helpful_role(fleet["role"], academy)
        ),
        "hulls": hulls,
    }


def kill_breakdown(
    characters: list[EveCharacter], days: int = WINDOW_DAYS
) -> dict[str, Any]:
    """Kills by gang size, losses, the hull on kills and the last kill.

    A mail counts once per person, however many of their alts were on it.
    """
    character_ids = [character.character_id for character in characters]
    cutoff = timezone.now() - timedelta(days=days)
    attacker_rows = list(
        EveCharacterKillmailAttacker.objects.filter(
            character_id__in=character_ids
        ).values_list("killmail_id", "ship_type_id")
    )
    killmail_ids = list({killmail_id for killmail_id, _ in attacker_rows})
    recent: dict = {}
    for chunk in _chunks(killmail_ids):
        recent.update(
            EveCharacterKillmail.objects.filter(
                id__in=chunk, killmail_time__gte=cutoff
            )
            .exclude(victim_character_id__in=character_ids)
            .values_list("id", "killmail_time")
        )
    attackers: dict = {}
    for chunk in _chunks(list(recent)):
        attackers.update(
            EveCharacterKillmailAttacker.objects.filter(killmail_id__in=chunk)
            .values("killmail_id")
            .annotate(n=Count("id"))
            .values_list("killmail_id", "n")
        )
    solo = small = fleet = 0
    for killmail_id in recent:
        size = attackers.get(killmail_id, 1)
        if size <= SOLO_MAX_ATTACKERS:
            solo += 1
        elif size <= SMALL_GANG_MAX_ATTACKERS:
            small += 1
        else:
            fleet += 1
    hulls = Counter(
        ship_type_id
        for killmail_id, ship_type_id in {
            (killmail_id, ship_type_id)
            for killmail_id, ship_type_id in attacker_rows
            if killmail_id in recent and ship_type_id
        }
    )
    losses = (
        EveCharacterKillmail.objects.filter(
            character__in=characters,
            victim_character_id__in=character_ids,
            killmail_time__gte=cutoff,
        )
        .values("killmail_id")
        .distinct()
        .count()
    )
    top = hulls.most_common(1)
    return {
        "solo": solo,
        "small_gang": small,
        "fleet": fleet,
        "losses": losses,
        "top_ship_type_id": top[0][0] if top else None,
        "last_kill_at": max(recent.values()) if recent else None,
    }


def _chunks(items: list, size: int = 5000):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def trial_progress(
    payload: Optional[dict], user_id: int, corporation_id: Optional[int]
) -> Optional[dict]:
    """Day of trial, review day, corp average and pace; None when not on trial."""
    row = trial_row(payload, user_id)
    if row is None:
        return None
    length = corp_trial_length(payload, corporation_id)
    return {
        "day": row.get("alliance_days"),
        "review_day": MIN_APPROVE_DAYS,
        "scale_days": TRIAL_SCALE_DAYS,
        "average_days": length["days"] if length else None,
        "average_scope": length["scope"] if length else None,
        "on_pace": row.get("decision") in ON_PACE_DECISIONS,
    }


def user_characters(user_id: int) -> list[EveCharacter]:
    return list(
        EveCharacter.objects.filter(user_id=user_id).only(
            "id", "character_id", "user_id", "corporation_id"
        )
    )


def is_on_trial(user) -> bool:
    return UserCommunityStatus.objects.filter(
        user=user, status=UserCommunityStatus.STATUS_TRIAL
    ).exists()


def pilot_report(user, corporation_id: Optional[int]) -> dict[str, Any]:
    """The Trial tab for the signed-in pilot."""
    payload = latest_payload()
    academy = is_academy(user)
    characters = user_characters(user.id)
    fleets = fleet_ships([c.character_id for c in characters])
    return {
        "trial": trial_progress(payload, user.id, corporation_id),
        "compare": compare_user(payload, user.id),
        "academy": academy,
        "ships": ships_summary(fleets, academy),
        "fleets": [
            {**fleet, "helpful": helpful_role(fleet["role"], academy)}
            for fleet in fleets[:RECENT_FLEETS]
        ],
    }


def member_insights(
    character: EveCharacter, corporation_id: Optional[int]
) -> dict[str, Any]:
    """The corp Members row: tiers, trial progress, ships and kills.

    A linked character stands for its person (every alt folded in); an
    unlinked one only for itself, with no tiers or trial.
    """
    user = character.user if character.user_id else None
    characters = user_characters(user.id) if user else [character]
    academy = is_academy(user) if user else False
    fleets = fleet_ships([c.character_id for c in characters])
    payload = latest_payload() if user else None
    kills = kill_breakdown(characters)
    kills["top_ship_name"] = _type_name(kills["top_ship_type_id"])
    return {
        "trial": (
            trial_progress(payload, user.id, corporation_id) if user else None
        ),
        "compare": compare_user(payload, user.id) if user else None,
        "academy": academy,
        "ships": ships_summary(fleets, academy),
        "kills": kills,
    }


def _type_name(type_id: Optional[int]) -> Optional[str]:
    # Imported here: eveuniverse models load late in some management paths.
    from eveuniverse.models import (  # pylint: disable=import-outside-toplevel
        EveType,
    )

    if not type_id:
        return None
    return (
        EveType.objects.filter(id=type_id)
        .values_list("name", flat=True)
        .first()
    )
