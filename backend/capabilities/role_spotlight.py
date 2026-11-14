"""
Fleet Roles guides: who flies a role, and recent fleets that flew it.

Both come from data the site already keeps, so the guides name real pilots
and real fights without anyone writing them: fleet members carry the ship
they flew, so the pilots are those who flew the role's ladder hulls on the
most fleets this year, and the fleets are recent ones that brought the most. Only fleets anyone in the alliance may see are
used (no private or members-only group fleets). Cached for an hour.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from app.cache import cache_get, cache_set
from eveonline.models import EveCharacter
from fleets.helpers.visibility import alliance_fleets_q
from fleets.models import EveFleet, EveFleetInstanceMember
from learning.models import MentorProfile

RECENT_DAYS = 60
PILOT_DAYS = 365
LIMIT = 5
CACHE_SECONDS = 60 * 60
CACHE_VERSION = 4


def role_spotlight(capabilities: list[str], ship_type_ids: list[int]) -> dict:
    capabilities = sorted(set(capabilities))[:4]
    ship_type_ids = sorted(set(ship_type_ids))[:12]
    key = (
        f"role_spotlight:v{CACHE_VERSION}:"
        f"{','.join(capabilities)}:{','.join(map(str, ship_type_ids))}"
    )
    cached = cache_get(key)
    if cached is not None:
        return cached
    fleets, days = _fleets(ship_type_ids, RECENT_DAYS), RECENT_DAYS
    if not fleets:
        # A quiet role still shows real fights: widen to the year.
        fleets, days = _fleets(ship_type_ids, PILOT_DAYS), PILOT_DAYS
    result = {
        "mentors": _mentors(ship_type_ids),
        "pilots": _pilots(ship_type_ids),
        "fleets": fleets,
        "fleets_days": days,
    }
    cache_set(key, result, CACHE_SECONDS)
    return result


def _pilots(ship_type_ids: list[int]) -> list[dict]:
    """The characters who flew these hulls on the most fleets this year."""
    if not ship_type_ids:
        return []
    since = timezone.now() - timedelta(days=PILOT_DAYS)
    rows = (
        EveFleetInstanceMember.objects.filter(
            ship_type_id__in=ship_type_ids,
            eve_fleet_instance__end_time__isnull=False,
            eve_fleet_instance__start_time__gte=since,
            eve_fleet_instance__eve_fleet__in=_visible_fleets(),
        )
        .values("character_id", "character_name")
        .annotate(fleets=Count("eve_fleet_instance__eve_fleet", distinct=True))
        .order_by("-fleets", "character_name")[: LIMIT * 2]
    )
    out, seen = [], set()
    for row in rows:
        if row["character_id"] in seen:
            continue
        seen.add(row["character_id"])
        out.append(
            {
                "character_id": row["character_id"],
                "name": row["character_name"],
                "fleets": row["fleets"],
            }
        )
        if len(out) == LIMIT:
            break
    return out


def _mentors(ship_type_ids: list[int]) -> list[dict]:
    """
    Approved mentors taking requests whose characters flew these hulls this
    year, most fleets first: the people to ask about this role by name.
    """
    if not ship_type_ids:
        return []
    mentor_users = set(
        MentorProfile.objects.filter(
            status=MentorProfile.STATUS_APPROVED, taking_requests=True
        ).values_list("user_id", flat=True)
    )
    if not mentor_users:
        return []
    characters = {
        c.character_id: c
        for c in EveCharacter.objects.filter(user_id__in=mentor_users)
    }
    if not characters:
        return []
    since = timezone.now() - timedelta(days=PILOT_DAYS)
    rows = (
        EveFleetInstanceMember.objects.filter(
            character_id__in=list(characters),
            ship_type_id__in=ship_type_ids,
            eve_fleet_instance__end_time__isnull=False,
            eve_fleet_instance__start_time__gte=since,
            eve_fleet_instance__eve_fleet__in=_visible_fleets(),
        )
        .values("character_id")
        .annotate(fleets=Count("eve_fleet_instance__eve_fleet", distinct=True))
        .order_by("-fleets")
    )
    out, seen_users = [], set()
    for row in rows:
        character = characters[row["character_id"]]
        if character.user_id in seen_users:
            continue
        seen_users.add(character.user_id)
        out.append(
            {
                "character_id": character.character_id,
                "name": character.character_name,
                "fleets": row["fleets"],
            }
        )
        if len(out) == LIMIT:
            break
    return out


def _visible_fleets():
    """Fleets anyone in the alliance may see, never cancelled ones."""
    return EveFleet.objects.filter(alliance_fleets_q()).exclude(
        status="cancelled"
    )


def _fleets(ship_type_ids: list[int], days: int) -> list[dict]:
    """Recent finished fleets where pilots flew these hulls, most first."""
    if not ship_type_ids:
        return []
    since = timezone.now() - timedelta(days=days)
    visible = _visible_fleets()
    counts = (
        EveFleetInstanceMember.objects.filter(
            ship_type_id__in=ship_type_ids,
            eve_fleet_instance__end_time__isnull=False,
            eve_fleet_instance__start_time__gte=since,
            eve_fleet_instance__eve_fleet__in=visible,
        )
        .values("eve_fleet_instance__eve_fleet_id")
        .annotate(pilots=Count("character_id", distinct=True))
        .order_by("-pilots", "-eve_fleet_instance__eve_fleet_id")[:LIMIT]
    )
    pilots = {
        row["eve_fleet_instance__eve_fleet_id"]: row["pilots"]
        for row in counts
    }
    fleets = EveFleet.objects.filter(pk__in=pilots).select_related("doctrine")
    out = [
        {
            "fleet_id": fleet.pk,
            "start_time": fleet.start_time,
            "type": fleet.get_type_display(),
            "objective": fleet.objective or "",
            "doctrine": fleet.doctrine.name if fleet.doctrine else None,
            "pilots_in_role": pilots[fleet.pk],
        }
        for fleet in fleets
    ]
    out.sort(key=lambda f: (-f["pilots_in_role"], -f["fleet_id"]))
    return out
