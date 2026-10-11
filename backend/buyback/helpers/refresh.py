"""Orchestrate full buyback ledger + metrics refresh."""

from __future__ import annotations

import logging

from buyback.helpers.contracts_ledger import (
    backfill_contract_counterparties,
    sync_contract_ledger_entries,
)
from buyback.helpers.hangar import fetch_stockpile_quantities
from buyback.helpers.metrics import refresh_accepted_item_metrics
from buyback.helpers.purchase_orders import (
    try_complete_from_outbound_contracts,
)
from buyback.helpers.sell_orders import sync_sold_order_ledger_entries
from buyback.helpers.unknown import (
    emit_unknown_from_snapshots,
    take_hangar_snapshot,
)
from buyback.models import BuybackHangarSnapshot

logger = logging.getLogger(__name__)


def refresh_buyback_ledger(
    *,
    sync_contracts: bool = True,
    sync_sell_orders: bool = True,
    snapshot_hangar: bool = True,
    refresh_metrics: bool = True,
    seed_allowlist: bool = True,
) -> dict:
    """Full ledger pass used by the management command and Celery tasks."""
    result: dict = {}

    if sync_contracts:
        result["contracts"] = sync_contract_ledger_entries()
        result["counterparties"] = backfill_contract_counterparties()
        result["purchases_completed"] = try_complete_from_outbound_contracts()
        logger.info("Buyback contract ledger: %s", result["contracts"])
        logger.info(
            "Buyback contract counterparties: %s", result["counterparties"]
        )

    if sync_sell_orders:
        result["sell_orders"] = sync_sold_order_ledger_entries()
        logger.info("Buyback sell-order ledger: %s", result["sell_orders"])

    stockpile_qty = None
    if snapshot_hangar or refresh_metrics:
        stockpile_qty = fetch_stockpile_quantities()

    if snapshot_hangar:
        previous = BuybackHangarSnapshot.objects.order_by("-taken_at").first()
        current = take_hangar_snapshot(quantities=stockpile_qty or {})
        hangar_result = {
            "snapshot_id": current.pk,
            "types": len(current.quantities or {}),
            "unknown_created": 0,
        }
        if previous is not None:
            hangar_result["unknown_created"] = emit_unknown_from_snapshots(
                previous, current
            )["created"]
        result["hangar"] = hangar_result
        logger.info("Buyback hangar snapshot: %s", hangar_result)

    if refresh_metrics:
        result["metrics"] = refresh_accepted_item_metrics(
            stockpile_quantities=stockpile_qty,
            seed=seed_allowlist,
        )
        logger.info("Buyback metrics: %s", result["metrics"])

    return result
