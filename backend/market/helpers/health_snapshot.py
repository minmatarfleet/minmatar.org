"""Persist and read market health snapshots (local DB only, no ESI)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from market.helpers.contract_health import build_contract_health
from market.helpers.health_common import (
    market_active_locations,
    summary_fields,
)
from market.helpers.sell_order_health import build_sell_order_health
from market.models.health_snapshot import EveMarketHealthSnapshot

logger = logging.getLogger(__name__)

HISTORY_CHART_MAX_POINTS = 72
HISTORY_DAYS_MAX = 90
HISTORY_DAYS_DEFAULT = 30

SUMMARY_REQUIRED_KEYS = (
    "health_pct",
    "viability_pct",
    "targets",
    "fulfilled",
    "viable_fulfilled",
    "isk",
    "history_days",
)


@dataclass(frozen=True)
class HealthKindConfig:
    kind: str
    log_label: str
    build: Callable[..., dict]


CONTRACTS_KIND = HealthKindConfig(
    kind=EveMarketHealthSnapshot.KIND_CONTRACTS,
    log_label="contract health",
    build=build_contract_health,
)

SELL_ORDERS_KIND = HealthKindConfig(
    kind=EveMarketHealthSnapshot.KIND_SELL_ORDERS,
    log_label="sell-order health",
    build=build_sell_order_health,
)


def _parse_optional_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return parse_datetime(value)


def _require_summary(summary: dict) -> dict:
    missing = [key for key in SUMMARY_REQUIRED_KEYS if key not in summary]
    if missing:
        raise KeyError(
            f"health summary missing required keys: {', '.join(missing)}"
        )
    return summary


def record_health_snapshots(
    config: HealthKindConfig,
    *,
    location_id: int | None = None,
) -> int:
    locations = market_active_locations(location_id)
    if not locations:
        logger.info(
            "%s snapshot skipped: no market-active locations "
            "(location_id=%s)",
            config.log_label,
            location_id,
        )
        return 0

    payload_by_location = config.build(location_id=location_id)["by_location"]

    created = 0
    for loc in locations:
        payload = payload_by_location.get(loc.location_id)
        if payload is None:
            continue
        summary = _require_summary(payload["summary"])
        EveMarketHealthSnapshot.objects.create(
            kind=config.kind,
            location=loc,
            health_pct=summary["health_pct"],
            viability_pct=summary["viability_pct"],
            targets=summary["targets"],
            fulfilled=summary["fulfilled"],
            viable_fulfilled=summary["viable_fulfilled"],
            isk=summary["isk"],
            synced_at=_parse_optional_dt(payload.get("synced_at")),
            history_days=summary["history_days"],
        )
        created += 1

    logger.info(
        "%s snapshot recorded: location_id=%s rows=%s",
        config.log_label,
        location_id,
        created,
    )
    return created


def record_contract_health_snapshots(
    *,
    location_id: int | None = None,
) -> int:
    return record_health_snapshots(CONTRACTS_KIND, location_id=location_id)


def record_sell_order_health_snapshots(
    *,
    location_id: int | None = None,
) -> int:
    return record_health_snapshots(SELL_ORDERS_KIND, location_id=location_id)


def _downsample_asc(snaps: list, max_points: int) -> list:
    n = len(snaps)
    if n <= max_points:
        return snaps
    if max_points == 1:
        return [snaps[-1]]
    indices = sorted(
        {round(i * (n - 1) / (max_points - 1)) for i in range(max_points)}
    )
    return [snaps[i] for i in indices]


def _serialize_latest(snap: EveMarketHealthSnapshot) -> dict:
    return {
        "id": snap.id,
        "captured_at": snap.captured_at.isoformat(),
        "location_id": snap.location.location_id,
        "location_name": snap.location.location_name,
        "short_name": snap.location.short_name or "",
        **summary_fields(snap),
    }


def _serialize_history(snap: EveMarketHealthSnapshot) -> dict:
    return {
        "id": snap.id,
        "captured_at": snap.captured_at.isoformat(),
        **summary_fields(snap),
    }


def _latest_for_location(kind: str, location_id: int):
    return (
        EveMarketHealthSnapshot.objects.select_related("location")
        .filter(kind=kind, location__location_id=location_id)
        .order_by("-captured_at")
        .first()
    )


def _history_for_location(
    kind: str,
    *,
    location_id: int,
    days: int,
    max_points: int = HISTORY_CHART_MAX_POINTS,
) -> list[EveMarketHealthSnapshot]:
    days = max(1, min(int(days), HISTORY_DAYS_MAX))
    max_points = max(1, min(int(max_points), HISTORY_CHART_MAX_POINTS))
    since = timezone.now() - timedelta(days=days)
    snaps_asc = list(
        EveMarketHealthSnapshot.objects.select_related("location")
        .filter(
            kind=kind,
            location__location_id=location_id,
            captured_at__gte=since,
        )
        .order_by("captured_at")
    )
    snaps_asc = _downsample_asc(snaps_asc, max_points)
    snaps_asc.reverse()
    return snaps_asc


def _get_kind_health(
    kind: str,
    *,
    location_id: int,
    days: int,
) -> dict:
    latest = _latest_for_location(kind, location_id)
    history = _history_for_location(
        kind,
        location_id=location_id,
        days=days,
    )
    return {
        "latest": _serialize_latest(latest) if latest is not None else None,
        "history": [_serialize_history(snap) for snap in history],
    }


def get_contract_health(
    *,
    location_id: int,
    days: int = HISTORY_DAYS_DEFAULT,
) -> dict:
    return _get_kind_health(
        EveMarketHealthSnapshot.KIND_CONTRACTS,
        location_id=location_id,
        days=days,
    )


def get_sell_order_health(
    *,
    location_id: int,
    days: int = HISTORY_DAYS_DEFAULT,
) -> dict:
    return _get_kind_health(
        EveMarketHealthSnapshot.KIND_SELL_ORDERS,
        location_id=location_id,
        days=days,
    )


def _merge_chart_history(
    contracts_history: list[dict],
    sell_orders_history: list[dict],
) -> list[dict]:
    """
    As-of join of independent contract / sell-order history series.

    At each unique capture time, carry forward the latest known value from
    each series (writers run on different clocks).
    Returns newest-first to match other history payloads.
    """
    contracts_asc = list(reversed(contracts_history))
    sell_asc = list(reversed(sell_orders_history))
    times = sorted(
        {point["captured_at"] for point in contracts_asc}
        | {point["captured_at"] for point in sell_asc}
    )
    if not times:
        return []

    ci = 0
    si = 0
    last_c: dict | None = None
    last_s: dict | None = None
    merged: list[dict] = []
    for captured_at in times:
        while (
            ci < len(contracts_asc)
            and contracts_asc[ci]["captured_at"] <= captured_at
        ):
            last_c = contracts_asc[ci]
            ci += 1
        while (
            si < len(sell_asc) and sell_asc[si]["captured_at"] <= captured_at
        ):
            last_s = sell_asc[si]
            si += 1
        merged.append(
            {
                "captured_at": captured_at,
                "contracts_health_pct": (
                    last_c["health_pct"] if last_c else None
                ),
                "contracts_viability_pct": (
                    last_c["viability_pct"] if last_c else None
                ),
                "sell_orders_health_pct": (
                    last_s["health_pct"] if last_s else None
                ),
                "sell_orders_viability_pct": (
                    last_s["viability_pct"] if last_s else None
                ),
            }
        )
    merged.reverse()
    return merged


def get_market_health(
    *,
    location_id: int,
    days: int = HISTORY_DAYS_DEFAULT,
) -> dict:
    contracts = get_contract_health(location_id=location_id, days=days)
    sell_orders = get_sell_order_health(location_id=location_id, days=days)
    return {
        "contracts": contracts,
        "sell_orders": sell_orders,
        "chart": _merge_chart_history(
            contracts["history"], sell_orders["history"]
        ),
    }
