from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from django.db.models import Max, Q
from django.utils import timezone

from feed.constants import (
    ESI_FW_SYSTEMS_URL,
    FACTION_AMARR,
    FACTION_MINMATAR,
    FEED_FW_ESI_USER_AGENT,
)
from feed.helpers.killmail_classify import faction_to_label
from feed.helpers.monitored_systems import get_monitored_system_ids
from feed.models import (
    FeedEvent,
    FeedMonitoredSystem,
    FeedSystemContestedSnapshot,
)
from feed.rollups.config import get_rollup_config, get_rollup_version
from feed.rollups.types import RollupResult
from feed.rollups.writer import write_rollup_results


@dataclass(frozen=True)
class FwSystemContested:
    solar_system_id: int
    contested_percent: float
    occupier_faction_id: int | None
    victor_faction_id: int | None


def contested_percent_from_esi_entry(entry: dict) -> float:
    """Derive contested % from ESI victory points (contested_percent field was removed)."""
    threshold = int(entry.get("victory_points_threshold") or 0)
    if threshold <= 0:
        return 0.0
    victory_points = int(entry.get("victory_points") or 0)
    if entry.get("contested") == "uncontested" and victory_points <= 0:
        return 0.0
    return min(100.0, (victory_points / threshold) * 100.0)


def fetch_fw_contested_from_esi() -> dict[int, FwSystemContested]:
    response = requests.get(
        ESI_FW_SYSTEMS_URL,
        headers={"User-Agent": FEED_FW_ESI_USER_AGENT},
        timeout=60,
    )
    response.raise_for_status()
    rows: dict[int, FwSystemContested] = {}
    for entry in response.json():
        system_id = entry.get("solar_system_id")
        if not system_id:
            continue
        rows[int(system_id)] = FwSystemContested(
            solar_system_id=int(system_id),
            contested_percent=contested_percent_from_esi_entry(entry),
            occupier_faction_id=entry.get("occupier_faction_id"),
            victor_faction_id=entry.get("owner_faction_id"),
        )
    return rows


def _previous_snapshots(
    system_ids: frozenset[int],
    *,
    before,
) -> dict[int, FeedSystemContestedSnapshot]:
    if not system_ids:
        return {}
    latest_rows = (
        FeedSystemContestedSnapshot.objects.filter(
            solar_system_id__in=system_ids,
            captured_at__lt=before,
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


def _occupier_payload_key(
    occupier_faction_id: int | None,
    contested_percent: float,
) -> str:
    if 0 < contested_percent < 100:
        return "contested"
    if occupier_faction_id == FACTION_MINMATAR:
        return "minmatar"
    if occupier_faction_id == FACTION_AMARR:
        return "amarr"
    return "contested"


def _accent_for_system(
    occupier_faction_id: int | None,
    contested_percent: float,
) -> str:
    if 0 < contested_percent < 100:
        return FeedEvent.Accent.COMBAT
    if occupier_faction_id == FACTION_MINMATAR:
        return FeedEvent.Accent.MILITIA
    if occupier_faction_id == FACTION_AMARR:
        return FeedEvent.Accent.AMARR
    return FeedEvent.Accent.COMBAT


def _holder_label(
    occupier_faction_id: int | None,
    contested_percent: float,
) -> str:
    if 0 < contested_percent < 100:
        return "Contested"
    if occupier_faction_id in (FACTION_MINMATAR, FACTION_AMARR):
        return faction_to_label(occupier_faction_id)
    return "Unknown holder"


def _format_delta(delta_percent: float) -> str:
    sign = "+" if delta_percent >= 0 else "−"
    return f"{sign}{abs(delta_percent):.1f}%"


def _build_contested_event(
    *,
    system_name: str,
    current: FwSystemContested,
    previous: FeedSystemContestedSnapshot,
    delta_percent: float,
    occurred_at,
    config: dict[str, Any],
) -> RollupResult:
    version = get_rollup_version("contested_change")
    window_hours = config.get("window_hours", 1)
    holder = _holder_label(
        current.occupier_faction_id, current.contested_percent
    )
    delta_label = _format_delta(delta_percent)
    hour_bucket = occurred_at.replace(minute=0, second=0, microsecond=0)
    cluster_key = (
        f"contested:{current.solar_system_id}:"
        f"{hour_bucket.strftime('%Y%m%dT%H')}"
    )
    direction = "up" if delta_percent >= 0 else "down"
    title = f"{system_name} contested {delta_label} this hour"
    subheader = f"{current.contested_percent:.1f}% contested · {holder}"
    preview = (
        f"Moved from {previous.contested_percent:.1f}% to "
        f"{current.contested_percent:.1f}% contested in the last hour."
    )
    return RollupResult(
        kind=FeedEvent.Kind.CONTESTED_CHANGE,
        occurred_at=occurred_at,
        title=title,
        subheader=subheader,
        preview=preview,
        body=preview,
        accent=_accent_for_system(
            current.occupier_faction_id,
            current.contested_percent,
        ),
        payload={
            "system_id": current.solar_system_id,
            "system_name": system_name,
            "contested_percent": round(current.contested_percent, 2),
            "previous_contested_percent": round(previous.contested_percent, 2),
            "delta_percent": round(delta_percent, 2),
            "delta_hours": window_hours,
            "direction": direction,
            "occupier_faction_id": current.occupier_faction_id,
            "occupier": _occupier_payload_key(
                current.occupier_faction_id,
                current.contested_percent,
            ),
        },
        rollup_code="contested_change",
        rollup_version=version,
        cluster_key=cluster_key,
    )


def poll_monitored_contested_snapshots(*, now=None) -> dict[str, int]:
    captured_at = now or timezone.now()
    monitored_ids = get_monitored_system_ids(force_refresh=True)
    if not monitored_ids:
        return {
            "monitored_systems": 0,
            "esi_systems_matched": 0,
            "snapshots_written": 0,
            "events_written": 0,
        }

    system_names = {
        row.solar_system_id: row.name
        for row in FeedMonitoredSystem.objects.filter(
            solar_system_id__in=monitored_ids,
            is_active=True,
        )
    }
    previous_by_system = _previous_snapshots(monitored_ids, before=captured_at)
    esi_rows = fetch_fw_contested_from_esi()
    matched = {
        system_id: esi_rows[system_id]
        for system_id in monitored_ids
        if system_id in esi_rows
    }

    FeedSystemContestedSnapshot.objects.bulk_create(
        [
            FeedSystemContestedSnapshot(
                solar_system_id=row.solar_system_id,
                contested_percent=row.contested_percent,
                occupier_faction_id=row.occupier_faction_id,
                victor_faction_id=row.victor_faction_id,
                captured_at=captured_at,
            )
            for row in matched.values()
        ]
    )

    config = get_rollup_config("contested_change")
    min_delta = float(config.get("min_delta_percent", 5.0))
    max_events = int(config.get("max_events_per_poll", 15))
    candidates: list[tuple[float, RollupResult]] = []
    for system_id, current in matched.items():
        previous = previous_by_system.get(system_id)
        if previous is None:
            continue
        delta_percent = current.contested_percent - previous.contested_percent
        if abs(delta_percent) < min_delta:
            continue
        candidates.append(
            (
                abs(delta_percent),
                _build_contested_event(
                    system_name=system_names.get(
                        system_id, f"System {system_id}"
                    ),
                    current=current,
                    previous=previous,
                    delta_percent=delta_percent,
                    occurred_at=captured_at,
                    config=config,
                ),
            )
        )

    candidates.sort(key=lambda row: row[0], reverse=True)
    results = [result for _, result in candidates[:max_events]]
    events_written = write_rollup_results(results)
    return {
        "monitored_systems": len(monitored_ids),
        "esi_systems_matched": len(matched),
        "snapshots_written": len(matched),
        "events_written": events_written,
    }
