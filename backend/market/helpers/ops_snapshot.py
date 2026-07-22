"""Persist ops monitor health from local DB after ESI syncs (no ESI here)."""

from __future__ import annotations

import logging
from datetime import datetime

from django.utils.dateparse import parse_datetime

from eveonline.models import EveLocation
from market.helpers.ops_monitor import build_ops_monitor
from market.models.ops_snapshot import EveMarketOpsMonitorSnapshot

logger = logging.getLogger(__name__)


def _parse_optional_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(value)
    return parsed


def _problem_contracts(rows: list[dict]) -> list[dict]:
    """Strip bulky fitting text; keep triage fields used by the ops API."""
    cleaned = []
    for row in rows:
        cleaned.append(
            {
                "location_id": row["location_id"],
                "location_name": row["location_name"],
                "short_name": row.get("short_name") or "",
                "fitting_id": row["fitting_id"],
                "fitting_name": row["fitting_name"],
                "ship_id": row["ship_id"],
                "current_quantity": row["current_quantity"],
                "expected_quantity": row["expected_quantity"],
                "shortfall": row["shortfall"],
                "readiness": row["readiness"],
                "expectation_id": row["expectation_id"],
            }
        )
    return cleaned


def _problem_sell_gaps(rows: list[dict]) -> list[dict]:
    return [
        {
            "location_id": row["location_id"],
            "location_name": row["location_name"],
            "short_name": row.get("short_name") or "",
            "type_id": row["type_id"],
            "item_name": row["item_name"],
            "current_quantity": row["current_quantity"],
            "viable_quantity": row["viable_quantity"],
            "expected_quantity": row["expected_quantity"],
            "shortfall": row["shortfall"],
            "ships": row.get("ships") or [],
        }
        for row in rows
    ]


def record_ops_monitor_snapshots(
    *,
    trigger: str,
    location_id: int | None = None,
) -> int:
    """
    Snapshot ops health for one or all market-active locations.

    Uses only local DB (orders, contracts, expectations). Does not call ESI.
    """
    if trigger not in {
        EveMarketOpsMonitorSnapshot.TRIGGER_CONTRACTS,
        EveMarketOpsMonitorSnapshot.TRIGGER_ORDERS,
    }:
        raise ValueError(f"Unknown ops snapshot trigger: {trigger}")

    locations = EveLocation.objects.filter(market_active=True)
    if location_id is not None:
        locations = locations.filter(location_id=location_id)
    locations = list(locations)
    if not locations:
        logger.info(
            "ops monitor snapshot skipped: no market-active locations "
            "(trigger=%s location_id=%s)",
            trigger,
            location_id,
        )
        return 0

    created = 0
    for loc in locations:
        payload = build_ops_monitor(location_id=loc.location_id)
        summary = payload["summary"]
        EveMarketOpsMonitorSnapshot.objects.create(
            location=loc,
            trigger=trigger,
            contracts_health_pct=summary.get("contracts_health_pct"),
            sell_orders_health_pct=summary.get("sell_orders_health_pct"),
            sell_orders_viability_pct=summary.get("sell_orders_viability_pct"),
            overall_health_pct=summary.get("overall_health_pct"),
            understocked_contracts_count=summary.get(
                "understocked_contracts", 0
            ),
            sell_gaps_count=summary.get("sell_gaps", 0),
            contract_targets=summary.get("contract_targets", 0),
            contract_fulfilled=summary.get("contract_fulfilled", 0),
            sell_order_targets=summary.get("sell_order_targets", 0),
            sell_order_fulfilled=summary.get("sell_order_fulfilled", 0),
            sell_order_viable_fulfilled=summary.get(
                "sell_order_viable_fulfilled", 0
            ),
            contracts_isk=summary.get("contracts_isk", 0.0),
            sell_orders_isk=summary.get("sell_orders_isk", 0.0),
            total_isk_on_market=summary.get("total_isk_on_market", 0.0),
            contracts_synced_at=_parse_optional_dt(
                payload.get("contracts_synced_at")
            ),
            orders_synced_at=_parse_optional_dt(
                payload.get("orders_synced_at")
            ),
            understocked_contracts=_problem_contracts(
                payload.get("understocked_contracts") or []
            ),
            sell_gaps=_problem_sell_gaps(payload.get("sell_gaps") or []),
        )
        created += 1

    logger.info(
        "ops monitor snapshot recorded: trigger=%s location_id=%s rows=%s",
        trigger,
        location_id,
        created,
    )
    return created


def list_ops_monitor_snapshots(
    *,
    location_id: int | None = None,
    limit: int = 48,
) -> list[dict]:
    """Return recent snapshots newest-first for the history API."""
    limit = max(1, min(limit, 200))
    qs = EveMarketOpsMonitorSnapshot.objects.select_related("location")
    if location_id is not None:
        qs = qs.filter(location__location_id=location_id)
    rows = []
    for snap in qs.order_by("-captured_at")[:limit]:
        rows.append(
            {
                "id": snap.id,
                "captured_at": snap.captured_at.isoformat(),
                "location_id": snap.location.location_id,
                "location_name": snap.location.location_name,
                "short_name": snap.location.short_name or "",
                "trigger": snap.trigger,
                "contracts_health_pct": snap.contracts_health_pct,
                "sell_orders_health_pct": snap.sell_orders_health_pct,
                "sell_orders_viability_pct": snap.sell_orders_viability_pct,
                "overall_health_pct": snap.overall_health_pct,
                "understocked_contracts_count": (
                    snap.understocked_contracts_count
                ),
                "sell_gaps_count": snap.sell_gaps_count,
                "contract_targets": snap.contract_targets,
                "contract_fulfilled": snap.contract_fulfilled,
                "sell_order_targets": snap.sell_order_targets,
                "sell_order_fulfilled": snap.sell_order_fulfilled,
                "sell_order_viable_fulfilled": (
                    snap.sell_order_viable_fulfilled
                ),
                "contracts_isk": snap.contracts_isk,
                "sell_orders_isk": snap.sell_orders_isk,
                "total_isk_on_market": snap.total_isk_on_market,
                "contracts_synced_at": (
                    snap.contracts_synced_at.isoformat()
                    if snap.contracts_synced_at
                    else None
                ),
                "orders_synced_at": (
                    snap.orders_synced_at.isoformat()
                    if snap.orders_synced_at
                    else None
                ),
                "understocked_contracts": snap.understocked_contracts,
                "sell_gaps": snap.sell_gaps,
            }
        )
    return rows
