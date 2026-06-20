from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from eveuniverse.models import EveConstellation, EveSolarSystem

from feed.helpers.fw_contested import _occupier_payload_key
from feed.models import (
    FeedKillmail,
    FeedMonitoredSystem,
    FeedSystemContestedSnapshot,
)

AMARR_FRONT_REGIONS = frozenset({10000036, 10000038})
MINMATAR_FRONT_REGIONS = frozenset({10000030, 10000042})
WARZONE_BRIEFING_FULL_WINDOW_RATIO = 0.8
CONTESTED_CARD_LIMIT = 2


@dataclass(frozen=True)
class WarzoneSystemRow:
    system_id: int
    system_name: str
    sun_type_id: int
    contested_percent: float
    delta_24h: float
    kills_24h: int
    front: Literal["amarr", "minmatar"]
    occupier: Literal["minmatar", "amarr", "contested"] | None


@dataclass(frozen=True)
class WarzoneBriefing:
    hot_kills: WarzoneSystemRow | None
    amarr_contested: list[WarzoneSystemRow]
    minmatar_contested: list[WarzoneSystemRow]
    changes_24h: list[WarzoneSystemRow]
    updated_at: datetime | None
    has_full_24h_window: bool


def _oldest_snapshots_in_window(
    system_ids: frozenset[int],
    *,
    window_start,
    before,
) -> dict[int, FeedSystemContestedSnapshot]:
    """Earliest snapshot per system within [window_start, before]."""
    if not system_ids:
        return {}
    oldest_rows = (
        FeedSystemContestedSnapshot.objects.filter(
            solar_system_id__in=system_ids,
            captured_at__gte=window_start,
            captured_at__lte=before,
        )
        .values("solar_system_id")
        .annotate(oldest_captured=Min("captured_at"))
    )
    lookup = {
        row["solar_system_id"]: row["oldest_captured"] for row in oldest_rows
    }
    if not lookup:
        return {}
    query = Q()
    for system_id, captured_at in lookup.items():
        query |= Q(solar_system_id=system_id, captured_at=captured_at)
    return {
        snapshot.solar_system_id: snapshot
        for snapshot in FeedSystemContestedSnapshot.objects.filter(query)
    }


def _snapshots_at_or_before(
    system_ids: frozenset[int],
    *,
    before,
) -> dict[int, FeedSystemContestedSnapshot]:
    if not system_ids:
        return {}
    latest_rows = (
        FeedSystemContestedSnapshot.objects.filter(
            solar_system_id__in=system_ids,
            captured_at__lte=before,
        )
        .values("solar_system_id")
        .annotate(latest_captured=Max("captured_at"))
    )
    lookup = {
        row["solar_system_id"]: row["latest_captured"] for row in latest_rows
    }
    if not lookup:
        return {}
    query = Q()
    for system_id, captured_at in lookup.items():
        query |= Q(solar_system_id=system_id, captured_at=captured_at)
    return {
        snapshot.solar_system_id: snapshot
        for snapshot in FeedSystemContestedSnapshot.objects.filter(query)
    }


def _front_for_region(region_id: int | None) -> Literal["amarr", "minmatar"]:
    if region_id in AMARR_FRONT_REGIONS:
        return "amarr"
    if region_id in MINMATAR_FRONT_REGIONS:
        return "minmatar"
    return "minmatar"


def _resolve_system_metadata(
    system_ids: frozenset[int],
) -> dict[int, tuple[int, Literal["amarr", "minmatar"]]]:
    if not system_ids:
        return {}
    systems = list(
        EveSolarSystem.objects.filter(id__in=system_ids).select_related(
            "eve_constellation"
        )
    )
    found = {system.id for system in systems}
    missing = system_ids - found
    for system_id in missing:
        system, _ = EveSolarSystem.objects.get_or_create_esi(id=system_id)
        systems.append(system)

    constellation_ids = {
        system.eve_constellation_id
        for system in systems
        if system.eve_constellation_id
    }
    region_by_constellation = {
        row["id"]: row["eve_region_id"]
        for row in EveConstellation.objects.filter(
            id__in=constellation_ids
        ).values("id", "eve_region_id")
    }

    metadata: dict[int, tuple[int, Literal["amarr", "minmatar"]]] = {}
    for system in systems:
        region_id = None
        if system.eve_constellation_id:
            region_id = region_by_constellation.get(
                system.eve_constellation_id
            )
        sun_type_id = 0
        if system.eve_star_id and system.eve_star:
            sun_type_id = system.eve_star.type_id or 0
        metadata[system.id] = (sun_type_id, _front_for_region(region_id))
    return metadata


def _kills_last_24h(
    system_ids: frozenset[int],
    *,
    window_start,
    now,
) -> dict[int, int]:
    if not system_ids:
        return {}
    rows = (
        FeedKillmail.objects.filter(
            solar_system_id__in=system_ids,
            killmail_time__gte=window_start,
            killmail_time__lte=now,
        )
        .values("solar_system_id")
        .annotate(count=Count("id"))
    )
    return {row["solar_system_id"]: row["count"] for row in rows}


def _row_from_snapshots(
    *,
    system_id: int,
    system_name: str,
    latest: FeedSystemContestedSnapshot,
    baseline: FeedSystemContestedSnapshot | None,
    kills_24h: int,
    sun_type_id: int,
    front: Literal["amarr", "minmatar"],
) -> WarzoneSystemRow:
    delta_24h = (
        latest.contested_percent - baseline.contested_percent
        if baseline is not None
        else 0.0
    )
    occupier = _occupier_payload_key(
        latest.occupier_faction_id,
        latest.contested_percent,
    )
    return WarzoneSystemRow(
        system_id=system_id,
        system_name=system_name,
        sun_type_id=sun_type_id,
        contested_percent=round(latest.contested_percent, 1),
        delta_24h=round(delta_24h, 1),
        kills_24h=kills_24h,
        front=front,
        occupier=occupier,
    )


def build_warzone_briefing(*, now=None) -> WarzoneBriefing:
    now = now or timezone.now()
    window_start = now - timedelta(hours=24)

    monitored = list(
        FeedMonitoredSystem.objects.filter(is_active=True).order_by("name")
    )
    if not monitored:
        return WarzoneBriefing(
            hot_kills=None,
            amarr_contested=[],
            minmatar_contested=[],
            changes_24h=[],
            updated_at=None,
            has_full_24h_window=False,
        )

    system_ids = frozenset(row.solar_system_id for row in monitored)
    names = {row.solar_system_id: row.name for row in monitored}

    latest_by_system = _snapshots_at_or_before(system_ids, before=now)
    baseline_by_system = _oldest_snapshots_in_window(
        system_ids, window_start=window_start, before=now
    )
    kills_by_system = _kills_last_24h(
        system_ids, window_start=window_start, now=now
    )
    metadata = _resolve_system_metadata(system_ids)

    rows: list[WarzoneSystemRow] = []
    updated_at = None
    for system_id in system_ids:
        latest = latest_by_system.get(system_id)
        if latest is None:
            continue
        if updated_at is None or latest.captured_at > updated_at:
            updated_at = latest.captured_at
        sun_type_id, front = metadata.get(system_id, (0, "minmatar"))
        rows.append(
            _row_from_snapshots(
                system_id=system_id,
                system_name=names.get(system_id, f"System {system_id}"),
                latest=latest,
                baseline=baseline_by_system.get(system_id),
                kills_24h=kills_by_system.get(system_id, 0),
                sun_type_id=sun_type_id,
                front=front,
            )
        )

    systems_with_full_window = sum(
        1
        for system_id in system_ids
        if system_id in baseline_by_system
        and baseline_by_system[system_id].captured_at
        <= window_start + timedelta(hours=1)
    )
    has_full_24h_window = (
        len(system_ids) > 0
        and systems_with_full_window / len(system_ids)
        >= WARZONE_BRIEFING_FULL_WINDOW_RATIO
    )

    hot_kills = max(rows, key=lambda row: row.kills_24h, default=None)
    if hot_kills is not None and hot_kills.kills_24h == 0:
        hot_kills = None

    def contested_on_front(
        front: Literal["amarr", "minmatar"],
    ) -> list[WarzoneSystemRow]:
        return sorted(
            [
                row
                for row in rows
                if row.front == front and 0 < row.contested_percent < 100
            ],
            key=lambda row: row.contested_percent,
            reverse=True,
        )[:CONTESTED_CARD_LIMIT]

    changes_24h = sorted(
        rows,
        key=lambda row: (abs(row.delta_24h), row.delta_24h, row.system_name),
        reverse=True,
    )

    return WarzoneBriefing(
        hot_kills=hot_kills,
        amarr_contested=contested_on_front("amarr"),
        minmatar_contested=contested_on_front("minmatar"),
        changes_24h=changes_24h,
        updated_at=updated_at,
        has_full_24h_window=has_full_24h_window,
    )
