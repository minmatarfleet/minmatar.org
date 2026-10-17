"""Tribe About page: a year of the tribe, rolled up from its groups.

Every number here comes from the group reports (12-month window) or from
scans of killmails, fleets and mining ledgers, so it is far too slow for a
page request. Celery refreshes it; a request only reads the cache and, on a
miss, queues one refresh and renders without it (see ``tribe_about``).

Shared blocks (people, growth, corporations, each group's year and its top
pilots) work for any tribe. The Capitals and Supply tribes get one extra
block each that tells their own story; Pulse's story is its groups.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Any

from django.db.models import Count
from django.utils import timezone

from eveonline.helpers.corporations.safe_cache import (
    cache_add,
    cache_delete,
    cache_get,
    cache_set,
)
from eveonline.models import (
    EveCharacterAsset,
    EveCharacterKillmailAttacker,
    EveCharacterMiningEntry,
    EveCorporation,
)
from eveonline.models.characters import EvePlayer
from eveuniverse.models import EveSolarSystem, EveType
from fleets.models import EveFleetInstanceMember
from tribes.helpers.growth import tribe_membership_growth
from tribes.helpers.showcase import (
    PRIVATE_HIGHLIGHT_KEYS,
    _enrich_contributors,
)
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupRequirementAssetType,
)
from tribes.reports import ReportError, run_group_report
from tribes.reports.period import parse_period
from tribes.reports.registry import HIGHLIGHT_RUNNERS, binding_for_group
from tribes.reports.roster import roster_character_eve_ids
from tribes.reports.roster import roster_character_pks
from tribes.reports.types import ReportView

logger = logging.getLogger(__name__)

ABOUT_PERIOD = "12m"
ABOUT_TTL_SECONDS = 6 * 60 * 60
REFRESH_LOCK_SECONDS = 10 * 60
_ABOUT_KEY = "tribes:about:v1:{tribe_id}"
_LOCK_KEY = "tribes:about:refreshing:{tribe_id}"

TOP_PILOTS = 3
TOP_CORPORATIONS = 6

# The number each group's top pilots are ranked by.
GROUP_LEADER_METRIC = {
    "capitals.dreads": "kill_count",
    "capitals.carriers": "fleet_count",
    "capitals.faxes": "fleet_count",
    "supply.mining": "volume_m3",
    "supply.planetary-interaction": "isk_pi_30d_estimate",
    "supply.subcapital-production": "delivered_units",
    "supply.capital-production": "delivered_units",
    "supply.market": "fits_sold",
    "supply.loyalty-points": "lp",
    "pulse.advocates": "applications_accepted",
    "pulse.readiness": "doctrine_changes",
    "pulse.technology": "tickets_resolved",
    "pulse.thinkspeak": "pieces",
    "pulse.fishermen": "kill_count",
    "pulse.fleet-commanders": "fleet_count",
}

CAPITAL_CLASSES = frozenset(
    {
        "Dreadnought",
        "Lancer Dreadnought",
        "Carrier",
        "Force Auxiliary",
        "Supercarrier",
        "Titan",
    }
)
RECENT_CAPITAL_KILLS = 6
TOP_VICTIM_CLASSES = 6
TOP_SYSTEMS = 5
TOP_ORES = 5


def _month_keys(now, months: int = 12) -> list[str]:
    """The last ``months`` calendar months, oldest first, as YYYY-MM."""
    keys = []
    year, month = now.year, now.month
    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def _active_memberships(tribe: Tribe):
    return TribeGroupMembership.objects.filter(
        tribe_group__tribe=tribe,
        tribe_group__is_active=True,
        status=TribeGroupMembership.STATUS_ACTIVE,
    )


def _people(tribe: Tribe) -> dict[str, int]:
    per_user = Counter(
        _active_memberships(tribe).values_list("user_id", flat=True)
    )
    return {
        "people": len(per_user),
        "multi_group_people": sum(1 for n in per_user.values() if n > 1),
    }


def _corporations(tribe: Tribe) -> tuple[list[dict[str, Any]], int]:
    """Where the tribe's people come from, by their main's corporation."""
    user_ids = set(
        _active_memberships(tribe).values_list("user_id", flat=True)
    )
    corp_ids = Counter(
        corp_id
        for corp_id in EvePlayer.objects.filter(
            user_id__in=user_ids, primary_character__isnull=False
        ).values_list("primary_character__corporation_id", flat=True)
        if corp_id
    )
    corps = {
        c.corporation_id: c
        for c in EveCorporation.objects.filter(
            corporation_id__in=list(corp_ids)
        ).only("corporation_id", "name", "ticker")
    }
    rows = []
    for corp_id, people in corp_ids.most_common(TOP_CORPORATIONS):
        corp = corps.get(corp_id)
        rows.append(
            {
                "corporation_id": corp_id,
                "name": corp.name if corp else "",
                "ticker": corp.ticker if corp else "",
                "people": people,
            }
        )
    return rows, len(corp_ids)


def _run_year_report(group: TribeGroup):
    try:
        return run_group_report(
            group,
            view=ReportView.TOWN_HALL.value,
            period=ABOUT_PERIOD,
            scope="roster",
        )
    except ReportError as exc:
        # Freight is measured across the whole program, not a roster.
        if "program scope" in str(exc).lower():
            return run_group_report(
                group, view=ReportView.TOWN_HALL.value, period=ABOUT_PERIOD
            )
        raise


def _year_highlights(group: TribeGroup) -> dict[str, Any]:
    binding = binding_for_group(group)
    runner = HIGHLIGHT_RUNNERS.get(binding.highlights) if binding else None
    if not runner:
        return {}
    highlights = runner(group, parse_period(ABOUT_PERIOD)) or {}
    return {
        key: value
        for key, value in highlights.items()
        if key not in PRIVATE_HIGHLIGHT_KEYS
    }


def _top_pilots(group: TribeGroup, rows: list[dict]) -> list[dict[str, Any]]:
    metric = GROUP_LEADER_METRIC.get(group.code or "")
    if not metric:
        return []
    for row in rows:
        # Production rows name the main under a different key.
        if "primary_character" in row and "primary_character_name" not in row:
            row["primary_character_name"] = row["primary_character"]
    ranked = sorted(
        _enrich_contributors(rows, metric),
        key=lambda c: c["metric_value"] or 0,
        reverse=True,
    )
    return [
        {
            "character_id": c["character_id"],
            "character_name": c["character_name"],
            "value": c["metric_value"],
        }
        for c in ranked[:TOP_PILOTS]
    ]


def _group_year(group: TribeGroup) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": group.pk,
        "code": group.code or "",
        "name": group.name,
        "member_count": TribeGroupMembership.objects.filter(
            tribe_group=group, status=TribeGroupMembership.STATUS_ACTIVE
        ).count(),
        "roster_hidden": bool(group.roster_hidden),
        "manual": False,
        "totals": {},
        "highlights": {},
        "top_pilots": [],
    }
    if not binding_for_group(group):
        entry["manual"] = True
        return entry
    try:
        result = _run_year_report(group)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Tribe about: year report failed for %s", group.code)
        return entry
    if result.manual:
        entry["manual"] = True
        return entry
    entry["totals"] = result.totals or {}
    entry["top_pilots"] = _top_pilots(group, list(result.rows or []))
    try:
        entry["highlights"] = _year_highlights(group)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Tribe about: highlights failed for %s", group.code)
    return entry


def _type_groups(type_ids) -> dict[int, tuple[str, str]]:
    """type id -> (type name, group name)."""
    return {
        row["id"]: (row["name"], row["eve_group__name"] or "")
        for row in EveType.objects.filter(id__in=set(type_ids)).values(
            "id", "name", "eve_group__name"
        )
    }


def _system_names(system_ids) -> dict[int, str]:
    return dict(
        EveSolarSystem.objects.filter(id__in=set(system_ids)).values_list(
            "id", "name"
        )
    )


def capitals_block(groups: list[TribeGroup], now=None) -> dict[str, Any]:
    """The capital line: hulls on roster, what they killed, how they turn out."""
    now = now or timezone.now()
    year_ago = now - timedelta(days=365)
    hull_groups: dict[int, TribeGroup] = {}
    for group in groups:
        for type_id in TribeGroupRequirementAssetType.objects.filter(
            requirement__tribe_group=group, eve_type_id__isnull=False
        ).values_list("eve_type_id", flat=True):
            hull_groups.setdefault(type_id, group)
    if not hull_groups:
        return {}

    char_pks: set[int] = set()
    char_eve_ids: set[int] = set()
    for group in groups:
        char_pks |= roster_character_pks(group)
        char_eve_ids |= roster_character_eve_ids(group)

    # Hangar: every qualifying hull the tribe's characters own.
    owned = Counter(
        dict(
            EveCharacterAsset.objects.filter(
                character_id__in=char_pks, type_id__in=list(hull_groups)
            )
            .values("type_id")
            .annotate(n=Count("id"))
            .values_list("type_id", "n")
        )
    )
    type_info = _type_groups(hull_groups)
    hangar = []
    for group in groups:
        hulls = sorted(
            (
                {
                    "type_id": type_id,
                    "name": type_info.get(type_id, ("", ""))[0],
                    "count": owned.get(type_id, 0),
                }
                for type_id, g in hull_groups.items()
                if g.pk == group.pk
            ),
            key=lambda h: (-h["count"], h["name"]),
        )
        hangar.append(
            {
                "group_id": group.pk,
                "code": group.code or "",
                "name": group.name,
                "total": sum(h["count"] for h in hulls),
                "hulls": hulls,
            }
        )

    # Kills: one per killmail, whichever of our capitals were on it.
    attackers = (
        EveCharacterKillmailAttacker.objects.filter(
            character_id__in=char_eve_ids,
            ship_type_id__in=list(hull_groups),
        )
        .values_list(
            "killmail__killmail_id",
            "killmail__killmail_time",
            "killmail__ship_type_id",
            "killmail__solar_system_id",
            "killmail__victim_character_id",
            "character_id",
        )
        .iterator()
    )
    kills: dict[int, tuple] = {}
    for km_id, at, ship_type, system, victim, char_id in attackers:
        if char_id != victim:
            kills.setdefault(km_id, (at, ship_type, system))
    year_kills = {k: v for k, v in kills.items() if v[0] >= year_ago}
    victim_types = _type_groups(v[1] for v in year_kills.values())
    months = _month_keys(now)
    by_month = Counter(v[0].strftime("%Y-%m") for v in year_kills.values())
    classes = Counter(
        victim_types.get(v[1], ("", "Unknown"))[1] or "Unknown"
        for v in year_kills.values()
    )
    systems = Counter(v[2] for v in year_kills.values() if v[2])
    system_names = _system_names(
        list(systems) + [v[2] for v in year_kills.values()]
    )
    capital_kills = sorted(
        (
            (km_id, v)
            for km_id, v in year_kills.items()
            if victim_types.get(v[1], ("", ""))[1] in CAPITAL_CLASSES
        ),
        key=lambda item: item[1][0],
        reverse=True,
    )

    # Fleets: distinct pilots in a qualifying hull per fleet.
    turnout: dict[int, set[int]] = defaultdict(set)
    fleet_info: dict[int, dict] = {}
    for fleet_id, char_id, start, system in (
        EveFleetInstanceMember.objects.filter(
            character_id__in=char_eve_ids,
            ship_type_id__in=list(hull_groups),
        )
        .values_list(
            "eve_fleet_instance_id",
            "character_id",
            "eve_fleet_instance__start_time",
            "solar_system_name",
        )
        .iterator()
    ):
        turnout[fleet_id].add(char_id)
        info = fleet_info.setdefault(fleet_id, {"start": start, "systems": []})
        if system and system not in info["systems"]:
            info["systems"].append(system)
    year_fleets = [
        fid
        for fid, info in fleet_info.items()
        if info["start"] and info["start"] >= year_ago
    ]
    record = None
    if turnout:
        record_id = max(turnout, key=lambda fid: len(turnout[fid]))
        info = fleet_info[record_id]
        record = {
            "pilots": len(turnout[record_id]),
            "date": info["start"].isoformat() if info["start"] else None,
            "systems": info["systems"][:3],
        }
    hours = [0] * 24
    for fid in year_fleets:
        hours[fleet_info[fid]["start"].hour] += 1

    return {
        "hangar": hangar,
        "kills_by_month": [
            {"month": key, "kills": by_month.get(key, 0)} for key in months
        ],
        "year_kills": len(year_kills),
        "all_time_kills": len(kills),
        "first_kill": (
            min(v[0] for v in kills.values()).isoformat() if kills else None
        ),
        "victim_classes": [
            {"name": name, "kills": n}
            for name, n in classes.most_common(TOP_VICTIM_CLASSES)
        ],
        "capital_kills_year": len(capital_kills),
        "recent_capital_kills": [
            {
                "killmail_id": km_id,
                "ship_type_id": v[1],
                "ship_name": victim_types.get(v[1], ("", ""))[0],
                "ship_class": victim_types.get(v[1], ("", ""))[1],
                "system": system_names.get(v[2], ""),
                "killed_at": v[0].isoformat(),
            }
            for km_id, v in capital_kills[:RECENT_CAPITAL_KILLS]
        ],
        "systems": [
            {"name": system_names.get(sid, ""), "kills": n}
            for sid, n in systems.most_common(TOP_SYSTEMS)
            if system_names.get(sid)
        ],
        "fleets_year": len(year_fleets),
        "median_turnout": (
            int(median(len(turnout[fid]) for fid in year_fleets))
            if year_fleets
            else 0
        ),
        "record_turnout": record,
        "hours": hours,
    }


def supply_block(groups: list[TribeGroup], now=None) -> dict[str, Any]:
    """Ore by month and by kind, from the Mining group's ledgers."""
    now = now or timezone.now()
    mining = next((g for g in groups if g.code == "supply.mining"), None)
    if not mining:
        return {}
    char_pks = roster_character_pks(mining)
    months = _month_keys(now)
    year, month = months[0].split("-")
    first_day = date(int(year), int(month), 1)
    rows = list(
        EveCharacterMiningEntry.objects.filter(
            character_id__in=char_pks, date__gte=first_day
        ).values_list("date", "eve_type_id", "quantity")
    )
    types = {
        row["id"]: (row["volume"] or 0, row["eve_group__name"] or "")
        for row in EveType.objects.filter(id__in={r[1] for r in rows}).values(
            "id", "volume", "eve_group__name"
        )
    }
    by_month: Counter = Counter()
    by_ore: Counter = Counter()
    for day, type_id, quantity in rows:
        volume, ore = types.get(type_id, (0, ""))
        m3 = (quantity or 0) * volume
        by_month[day.strftime("%Y-%m")] += m3
        if ore:
            by_ore[ore] += m3
    return {
        "mining_by_month": [
            {"month": key, "volume_m3": round(by_month.get(key, 0))}
            for key in months
        ],
        "ores": [
            {"name": name, "volume_m3": round(m3)}
            for name, m3 in by_ore.most_common(TOP_ORES)
        ],
    }


def compute_tribe_about(tribe: Tribe) -> dict[str, Any]:
    now = timezone.now()
    groups = list(
        TribeGroup.objects.filter(tribe=tribe, is_active=True).order_by("name")
    )
    period = parse_period(ABOUT_PERIOD)
    corporations, corporation_count = _corporations(tribe)
    payload: dict[str, Any] = {
        "tribe_id": tribe.pk,
        "slug": tribe.slug,
        "generated_at": now.isoformat(),
        "period_start": period.start.isoformat(),
        "period_end": period.end.isoformat(),
        **_people(tribe),
        "growth": tribe_membership_growth(tribe, now=now),
        "corporations": corporations,
        "corporation_count": corporation_count,
        "groups": [_group_year(group) for group in groups],
        "capitals": None,
        "supply": None,
    }
    if tribe.slug == "capitals":
        payload["capitals"] = capitals_block(groups, now) or None
    elif tribe.slug == "supply":
        payload["supply"] = supply_block(groups, now) or None
    return payload


def refresh_tribe_about(tribe: Tribe) -> dict[str, Any]:
    about = compute_tribe_about(tribe)
    cache_set(_ABOUT_KEY.format(tribe_id=tribe.pk), about, ABOUT_TTL_SECONDS)
    cache_delete(_LOCK_KEY.format(tribe_id=tribe.pk))
    return about


def tribe_about(tribe_id: int) -> dict[str, Any] | None:
    """Cached About payload, or None after queueing a refresh."""
    key = _ABOUT_KEY.format(tribe_id=tribe_id)
    about = cache_get(key)
    if about is not None:
        return about
    # cache.add is atomic, so only one request per window queues the work.
    if cache_add(
        _LOCK_KEY.format(tribe_id=tribe_id), True, REFRESH_LOCK_SECONDS
    ):
        _queue_refresh(tribe_id)
    # Eager Celery (tests) fills the cache during the call above.
    return cache_get(key)


def _queue_refresh(tribe_id: int) -> None:
    # Imported here: the task module imports this helper.
    from tribes.tasks import (  # pylint: disable=import-outside-toplevel
        refresh_tribe_about_page,
    )

    try:
        refresh_tribe_about_page.apply_async(args=[tribe_id])
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Could not queue tribe about refresh for %s", tribe_id
        )
        cache_delete(_LOCK_KEY.format(tribe_id=tribe_id))
