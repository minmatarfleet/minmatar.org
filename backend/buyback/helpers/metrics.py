"""Weekly demand intensity + stockpile metrics on accepted items."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from buyback.helpers.accepted_items import (
    DEFAULT_PI_LOOKBACK_DAYS,
    seed_accepted_items,
)
from buyback.helpers.demand import mineral_name_to_id_for_ores
from buyback.helpers.hangar import fetch_stockpile_quantities
from buyback.models import BuybackAcceptedItem
from industry.helpers.compressed_ore import ore_materials_per_portion
from industry.helpers.type_breakdown import (
    resolve_type_to_demand_import_leaves,
)
from industry.models import IndustryOrder


def demand_quantities_from_recent_orders(
    *, lookback_days: int = DEFAULT_PI_LOOKBACK_DAYS
) -> dict[int, int]:
    """type_id → aggregated 90d import-leaf quantity from industry orders."""
    since = timezone.now() - timedelta(days=lookback_days)
    totals: dict[int, int] = defaultdict(int)
    orders = IndustryOrder.objects.filter(
        created_at__gte=since
    ).prefetch_related("items__eve_type")
    for order in orders:
        for item in order.items.all():
            try:
                leaves = resolve_type_to_demand_import_leaves(
                    item.eve_type, item.quantity
                )
            except Exception:
                continue
            for type_id, qty in leaves.items():
                totals[int(type_id)] += int(qty)
    return dict(totals)


def demand_quantity_for_accepted_item(
    *,
    type_id: int,
    category: str,
    type_name: str,
    leaf_quantities: dict[int, int],
    mineral_name_to_id: dict[str, int] | None = None,
) -> int:
    """Demand qty for one allowlist row (ores sum intersecting mineral leaves)."""
    if category != BuybackAcceptedItem.Category.ORE:
        return int(leaf_quantities.get(type_id, 0))

    try:
        materials = ore_materials_per_portion(type_name)
    except Exception:
        return 0
    if not materials:
        return 0
    if mineral_name_to_id is None:
        mineral_name_to_id = mineral_name_to_id_for_ores([type_name])
    total = 0
    for mineral_name in materials:
        mineral_id = mineral_name_to_id.get(mineral_name)
        if mineral_id is None:
            continue
        total += int(leaf_quantities.get(mineral_id, 0))
    return total


def assign_demand_statuses(
    quantities_by_item_id: dict[int, int],
) -> dict[int, str]:
    """
    Map BuybackAcceptedItem.pk → demand_status.

    surplus if qty==0; among positive qtys, <= median → low, else high.
    """
    positive = sorted(qty for qty in quantities_by_item_id.values() if qty > 0)
    median = statistics.median(positive) if positive else 0
    result: dict[int, str] = {}
    for item_id, qty in quantities_by_item_id.items():
        if qty <= 0:
            result[item_id] = BuybackAcceptedItem.DemandStatus.SURPLUS
        elif qty <= median:
            result[item_id] = BuybackAcceptedItem.DemandStatus.LOW
        else:
            result[item_id] = BuybackAcceptedItem.DemandStatus.HIGH
    return result


@transaction.atomic
def refresh_accepted_item_metrics(
    *,
    lookback_days: int = DEFAULT_PI_LOOKBACK_DAYS,
    stockpile_quantities: dict[int, int] | None = None,
    seed: bool = True,
) -> dict[str, int]:
    """Seed allowlist (optional), then write demand + stockpile onto accepted items."""
    seed_result = {"created": 0, "updated": 0, "seeded": 0}
    if seed:
        seed_result = seed_accepted_items()

    leaf_quantities = demand_quantities_from_recent_orders(
        lookback_days=lookback_days
    )
    hangar_qty = (
        stockpile_quantities
        if stockpile_quantities is not None
        else fetch_stockpile_quantities()
    )

    active_items = list(
        BuybackAcceptedItem.objects.filter(active=True).select_related(
            "eve_type"
        )
    )
    ore_names = [
        item.eve_type.name
        for item in active_items
        if item.category == BuybackAcceptedItem.Category.ORE
    ]
    mineral_name_to_id = mineral_name_to_id_for_ores(ore_names)

    qty_by_pk: dict[int, int] = {}
    for item in active_items:
        qty_by_pk[item.pk] = demand_quantity_for_accepted_item(
            type_id=item.eve_type_id,
            category=item.category,
            type_name=item.eve_type.name,
            leaf_quantities=leaf_quantities,
            mineral_name_to_id=mineral_name_to_id,
        )
    status_by_pk = assign_demand_statuses(qty_by_pk)
    now = timezone.now()
    updated = 0
    for item in active_items:
        item.demand_quantity = qty_by_pk.get(item.pk, 0)
        item.demand_status = status_by_pk.get(
            item.pk, BuybackAcceptedItem.DemandStatus.SURPLUS
        )
        item.stockpile_quantity = int(hangar_qty.get(item.eve_type_id, 0))
        item.metrics_updated_at = now
        item.save(
            update_fields=[
                "demand_quantity",
                "demand_status",
                "stockpile_quantity",
                "metrics_updated_at",
            ]
        )
        updated += 1

    return {
        "seeded": seed_result.get("seeded", 0),
        "seed_created": seed_result.get("created", 0),
        "seed_updated": seed_result.get("updated", 0),
        "metrics_updated": updated,
    }
