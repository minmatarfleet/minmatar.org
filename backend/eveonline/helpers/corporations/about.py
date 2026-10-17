"""Rollups for the corporation About tab and the Members roster.

Everything here scans fleet attendance, corporation history, killmails and
tribe memberships, so it only runs inside the Celery stats refresh (see
stats_cache) and never in a page request.

Names shown are mains only: alts fold into their owner and are never named.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone

from django.db.models import Count, Max
from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.helpers.characters.identity import (
    owner_user_ids,
    primary_refs_for_users,
)
from eveonline.helpers.corporations.kills import ACTIVITY_DAYS, RecentKills
from eveonline.helpers.corporations.summary import ship_bucket
from eveonline.models import (
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCorporation,
)
from fleets.helpers.metrics import fleets_led_by_user, led_fleets
from fleets.models import EveFleetInstance, EveFleetInstanceMember
from tribes.models import TribeGroupMembership

WEEKS = 13
RECORD_DAYS = 365
FOUNDER_DAYS = 30
TOP_HULLS = 6
TOP_PILOTS = 5
TOP_TRIBE_GROUPS = 8
TITLE_MAX = 60

TENURE_BANDS = (
    ("two_years", 730),
    ("one_year", 365),
    ("three_months", 91),
    ("new", 0),
)

# "AUTZ (10:00 - 13:00)" in the corp's free-text timezones field.
_PRIME_WINDOW = re.compile(
    r"\b(AU|EU|US)TZ\b\s*\(\s*(\d{1,2})(?::\d{2})?\s*[-–]\s*(\d{1,2})(?::\d{2})?\s*\)",
    re.IGNORECASE,
)
# Declared zone -> the observed fleet-time bucket it lines up with.
ZONE_BUCKET = {"AU": "AP", "EU": "EU", "US": "US"}


def corporation_about(
    corporation: EveCorporation,
    characters: list[EveCharacter],
    observed: dict[int, list[str]],
    kills: RecentKills,
    now: datetime | None = None,
) -> dict:
    """The About tab's cached facts for one corporation."""
    now = now or timezone.now()
    owners = _owners(characters)
    mains = _mains(owners)
    stints = _stint_starts([c.character_id for c in characters], corporation)
    founded = corporation.date_founded or _earliest(stints.values())
    cutoff = now - timedelta(days=ACTIVITY_DAYS)
    record_cutoff = now - timedelta(days=RECORD_DAYS)
    attendance = list(
        EveFleetInstanceMember.objects.filter(
            character_id__in=list(owners),
            join_time__gte=record_cutoff,
        ).values_list(
            "character_id",
            "join_time",
            "eve_fleet_instance_id",
            "eve_fleet_instance__eve_fleet_id",
            "ship_type_id",
            "solar_system_name",
        )
    )
    recent = [row for row in attendance if row[1] and row[1] >= cutoff]
    return {
        "founded": founded.isoformat() if founded else None,
        "home_system": _home_system(recent),
        "heatmap": _heatmap(recent, owners),
        "prime_windows": prime_windows(corporation.timezones, observed),
        "tenure": _tenure(mains, stints, now),
        "founders": _founders(mains, stints, founded),
        "hulls": _top_hulls(recent, owners),
        "records": _records(attendance, owners),
        "leaderboards": _leaderboards(
            corporation, characters, owners, mains, recent, kills, cutoff, now
        ),
        "tribe_groups": _tribe_groups({o for o in owners.values() if o > 0}),
    }


def member_facts(
    characters: list[EveCharacter],
    corporation: EveCorporation,
    now: datetime | None = None,
) -> dict[int, dict]:
    """Per character: in-corp since and last fleet. Fleet counts and the
    top hull are per person (alts folded together, each fleet once), and
    repeated on every character that person owns."""
    now = now or timezone.now()
    ids = [c.character_id for c in characters]
    owners = _owners(characters)
    stints = _stint_starts(ids, corporation)
    week_start = now - timedelta(weeks=WEEKS)
    cutoff = now - timedelta(days=ACTIVITY_DAYS)
    weeks: dict[int, list[set]] = defaultdict(
        lambda: [set() for _ in range(WEEKS)]
    )
    recent: dict[int, set] = defaultdict(set)
    hulls: dict[int, Counter] = defaultdict(Counter)
    rows = EveFleetInstanceMember.objects.filter(
        character_id__in=ids,
        join_time__gte=min(week_start, cutoff),
    ).values_list(
        "character_id", "join_time", "eve_fleet_instance_id", "ship_type_id"
    )
    for character_id, join_time, instance_id, ship_type_id in rows:
        if join_time is None:
            continue
        owner = owners[character_id]
        if join_time >= cutoff:
            recent[owner].add(instance_id)
        if join_time >= week_start:
            age = (now - join_time).days // 7
            weeks[owner][max(0, WEEKS - 1 - age)].add(instance_id)
            if ship_type_id:
                hulls[owner][ship_type_id] += 1
    last = dict(
        EveFleetInstanceMember.objects.filter(character_id__in=ids)
        .values("character_id")
        .annotate(last=Max("join_time"))
        .values_list("character_id", "last")
    )
    all_types = set().union(set(), *(set(c) for c in hulls.values()))
    groups = dict(
        EveType.objects.filter(id__in=list(all_types)).values_list(
            "id", "eve_group__name"
        )
    )
    names = _type_names(all_types)
    top_hull = {}
    for owner, counter in hulls.items():
        top_hull[owner] = next(
            (
                type_id
                for type_id, _ in counter.most_common()
                if ship_bucket(groups.get(type_id), type_id) is not None
            ),
            None,
        )
    facts = {}
    for character_id in ids:
        owner = owners[character_id]
        top = top_hull.get(owner)
        facts[character_id] = {
            "corp_joined_at": _iso(stints.get(character_id)),
            "last_fleet_at": _iso(last.get(character_id)),
            "person_fleets_90d": len(recent.get(owner, ())),
            "weekly_fleets": (
                [len(week) for week in weeks[owner]]
                if owner in weeks
                else [0] * WEEKS
            ),
            "top_hull_id": top,
            "top_hull_name": names.get(top) if top else None,
        }
    return facts


def prime_windows(
    text: str | None, observed: dict[int, list[str]]
) -> list[dict]:
    """Prime-time windows parsed from the corp's timezone text, with the
    number of pilots seen flying in each matching fleet-time bucket."""
    if not text:
        return []
    pilots = Counter()
    for buckets in observed.values():
        for bucket in buckets:
            pilots[bucket] += 1
    windows = []
    seen = set()
    for match in _PRIME_WINDOW.finditer(text):
        zone = match.group(1).upper()
        start, end = int(match.group(2)) % 24, int(match.group(3)) % 24
        if zone in seen or start == end:
            continue
        seen.add(zone)
        windows.append(
            {
                "zone": zone,
                "start_hour": start,
                "end_hour": end,
                "pilots": pilots.get(ZONE_BUCKET[zone], 0),
            }
        )
    return windows


def _owners(characters: list[EveCharacter]) -> dict[int, int]:
    """character_id -> owning user id, or -character_id when unlinked, so
    alts fold together and unlinked characters count as their own person."""
    linked = owner_user_ids(c.character_id for c in characters)
    return {
        c.character_id: linked.get(c.character_id, -c.character_id)
        for c in characters
    }


def _mains(owners: dict[int, int]) -> dict[int, tuple[int, str]]:
    """user id -> (character id, name) of their main, only when the main is
    in this corporation."""
    return {
        user_id: main
        for user_id, main in primary_refs_for_users(
            owner for owner in owners.values() if owner > 0
        ).items()
        if main[0] in owners
    }


def _stint_starts(
    character_ids: list[int], corporation: EveCorporation
) -> dict[int, datetime]:
    """Start of each character's current stint in this corporation."""
    return dict(
        EveCharacterCorporationHistory.objects.filter(
            character__character_id__in=character_ids,
            corporation_id=corporation.corporation_id,
        )
        .values("character__character_id")
        .annotate(start=Max("start_date"))
        .values_list("character__character_id", "start")
    )


def _tenure(mains, stints, now) -> dict:
    days = [
        (now - stints[character_id]).days
        for character_id, _ in mains.values()
        if character_id in stints
    ]
    bands = {key: 0 for key, _ in TENURE_BANDS}
    for value in days:
        for key, floor in TENURE_BANDS:
            if value >= floor:
                bands[key] += 1
                break
    return {
        "mains": len(days),
        "average_days": round(sum(days) / len(days)) if days else None,
        "bands": [
            {"key": key, "count": bands[key]} for key, _ in TENURE_BANDS
        ],
    }


def _founders(mains, stints, founded) -> int:
    if founded is None:
        return 0
    limit = founded + timedelta(days=FOUNDER_DAYS)
    return sum(
        1
        for character_id, _ in mains.values()
        if character_id in stints and stints[character_id] <= limit
    )


def _home_system(recent) -> dict | None:
    systems = Counter(row[5] for row in recent if row[5])
    if not systems:
        return None
    name, count = systems.most_common(1)[0]
    return {"name": name, "share": round(count / sum(systems.values()), 2)}


def _heatmap(recent, owners) -> list[list[int]]:
    """Distinct people on fleets per EVE-time weekday (rows) and hour."""
    cells: dict[tuple[int, int], set] = defaultdict(set)
    for character_id, join_time, instance_id, *_ in recent:
        when = _eve_time(join_time)
        cells[(when.weekday(), when.hour)].add(
            (owners.get(character_id), instance_id)
        )
    return [
        [len(cells.get((day, hour), ())) for hour in range(24)]
        for day in range(7)
    ]


def _top_hulls(recent, owners) -> list[dict]:
    pilots: dict[int, set] = defaultdict(set)
    for character_id, _, _, _, ship_type_id, _ in recent:
        if ship_type_id:
            pilots[ship_type_id].add(owners.get(character_id))
    groups = dict(
        EveType.objects.filter(id__in=list(pilots)).values_list(
            "id", "eve_group__name"
        )
    )
    ranked = sorted(
        (
            (len(people), type_id)
            for type_id, people in pilots.items()
            if ship_bucket(groups.get(type_id), type_id) is not None
        ),
        key=lambda item: (-item[0], item[1]),
    )[:TOP_HULLS]
    names = _type_names({type_id for _, type_id in ranked})
    return [
        {"type_id": type_id, "name": names.get(type_id, ""), "pilots": count}
        for count, type_id in ranked
    ]


def _records(attendance, owners) -> dict:
    turnout: dict[int, set] = defaultdict(set)
    fleets_by_month: dict[str, set] = defaultdict(set)
    for character_id, join_time, instance_id, fleet_id, *_ in attendance:
        turnout[instance_id].add(owners.get(character_id))
        if join_time and fleet_id:
            fleets_by_month[_eve_time(join_time).strftime("%Y-%m")].add(
                fleet_id
            )
    biggest = None
    if turnout:
        instance_id, people = max(
            turnout.items(), key=lambda item: (len(item[1]), item[0])
        )
        fleet = (
            EveFleetInstance.objects.filter(id=instance_id)
            .values("eve_fleet__start_time", "eve_fleet__description")
            .first()
        )
        biggest = {
            "pilots": len(people),
            "date": _iso(fleet["eve_fleet__start_time"]) if fleet else None,
            "title": _title(fleet["eve_fleet__description"]) if fleet else "",
        }
    busiest = None
    if fleets_by_month:
        month, fleets = max(
            fleets_by_month.items(), key=lambda item: (len(item[1]), item[0])
        )
        busiest = {"month": month, "fleets": len(fleets)}
    return {"biggest_turnout": biggest, "busiest_month": busiest}


def _leaderboards(  # pylint: disable=too-many-arguments
    corporation, characters, owners, mains, recent, kills, cutoff, now
) -> dict:
    fleets: dict[int, set] = defaultdict(set)
    for character_id, _, instance_id, *_ in recent:
        fleets[owners[character_id]].add(instance_id)
    killmails: dict[int, set] = defaultdict(set)
    for character in characters:
        killmails[owners[character.character_id]] |= kills.killmails_for(
            [character.character_id]
        )
    led = Counter(
        dict(
            fleets_led_by_user(
                led_fleets(cutoff, now).filter(created_by_id__in=list(mains))
            ).values_list("created_by_id", "fleet_count")
        )
    )
    return {
        "fleets": _ranked({o: len(v) for o, v in fleets.items()}, mains),
        "kills": _ranked({o: len(v) for o, v in killmails.items()}, mains),
        "fleets_led": _ranked(dict(led), mains),
    }


def _ranked(values: dict[int, int], mains) -> list[dict]:
    """Top people by value, named by their main. People without a main in
    this corporation are left out rather than named by an alt."""
    rows = [
        (value, owner)
        for owner, value in values.items()
        if value > 0 and owner in mains
    ]
    rows.sort(key=lambda item: (-item[0], mains[item[1]][1].lower()))
    return [
        {
            "character_id": mains[owner][0],
            "character_name": mains[owner][1],
            "value": value,
        }
        for value, owner in rows[:TOP_PILOTS]
    ]


def _tribe_groups(user_ids: set[int]) -> list[dict]:
    if not user_ids:
        return []
    rows = (
        TribeGroupMembership.objects.filter(
            user_id__in=user_ids,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        .values("tribe_group_id", "tribe_group__name")
        .annotate(members=Count("user_id", distinct=True))
        .order_by("-members", "tribe_group__name")[:TOP_TRIBE_GROUPS]
    )
    return [
        {"name": row["tribe_group__name"], "members": row["members"]}
        for row in rows
    ]


def _type_names(type_ids) -> dict[int, str]:
    if not type_ids:
        return {}
    return dict(
        EveType.objects.filter(id__in=list(type_ids)).values_list("id", "name")
    )


def _title(description: str | None) -> str:
    first = (description or "").strip().splitlines()
    text = first[0].strip() if first else ""
    if len(text) > TITLE_MAX:
        text = text[: TITLE_MAX - 1].rstrip() + "…"
    return text


def _earliest(values) -> datetime | None:
    values = [v for v in values if v]
    return min(values) if values else None


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _eve_time(value: datetime) -> datetime:
    aware = timezone.make_aware(value) if timezone.is_naive(value) else value
    return aware.astimezone(dt_timezone.utc)
