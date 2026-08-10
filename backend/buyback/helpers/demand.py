"""Supply-chain demand set for buyback rates (recent order import leaves)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from eveuniverse.models import EveType

from buyback.helpers.accepted_items import DEFAULT_PI_LOOKBACK_DAYS
from buyback.models import BuybackAcceptedItem
from industry.helpers.compressed_ore import ore_materials_per_portion
from industry.helpers.type_breakdown import (
    resolve_type_to_demand_import_leaves,
)
from industry.models import IndustryOrder

RATE_REASON_SUPPLY_CHAIN = "supply_chain_import"
RATE_REASON_SURPLUS = "accepted_surplus"


def demand_type_ids_from_recent_orders(
    *, lookback_days: int = DEFAULT_PI_LOOKBACK_DAYS
) -> set[int]:
    """
    Distinct type IDs that are strategy-aware import leaves for industry
    orders created in the lookback window.
    """
    since = timezone.now() - timedelta(days=lookback_days)
    demand_ids: set[int] = set()
    orders = IndustryOrder.objects.filter(
        created_at__gte=since
    ).prefetch_related("items__eve_type")
    for order in orders:
        for item in order.items.all():
            try:
                demand_ids.update(
                    resolve_type_to_demand_import_leaves(
                        item.eve_type, item.quantity
                    )
                )
            except Exception:
                continue
    return demand_ids


def mineral_name_to_id_for_ores(ore_names: list[str]) -> dict[str, int]:
    """Map refined mineral name → EveType id for the given compressed ores."""
    mineral_names: set[str] = set()
    for ore_name in ore_names:
        try:
            mineral_names.update(ore_materials_per_portion(ore_name).keys())
        except Exception:
            continue
    if not mineral_names:
        return {}
    return dict(
        EveType.objects.filter(name__in=mineral_names).values_list(
            "name", "id"
        )
    )


def ore_intersects_demand(
    ore_name: str,
    demand_ids: set[int],
    *,
    mineral_name_to_id: dict[str, int] | None = None,
) -> bool:
    """True if any refined mineral from this compressed ore is in demand."""
    try:
        materials = ore_materials_per_portion(ore_name)
    except Exception:
        return False
    if not materials:
        return False
    if mineral_name_to_id is None:
        mineral_name_to_id = mineral_name_to_id_for_ores([ore_name])
    for mineral_name in materials:
        mineral_id = mineral_name_to_id.get(mineral_name)
        if mineral_id is not None and mineral_id in demand_ids:
            return True
    return False


def type_in_demand(
    *,
    type_id: int,
    category: str,
    type_name: str,
    demand_ids: set[int],
    mineral_name_to_id: dict[str, int] | None = None,
) -> bool:
    """Whether an accepted buyback type qualifies for the demand (full) rate."""
    if category == BuybackAcceptedItem.Category.ORE:
        return ore_intersects_demand(
            type_name,
            demand_ids,
            mineral_name_to_id=mineral_name_to_id,
        )
    return type_id in demand_ids


def rate_reason_for_in_demand(in_demand: bool) -> str:
    return RATE_REASON_SUPPLY_CHAIN if in_demand else RATE_REASON_SURPLUS


def stored_demand_by_type_id() -> dict[int, bool]:
    """type_id → in_demand from persisted BuybackAcceptedItem metrics."""
    return {
        item.eve_type_id: item.in_demand
        for item in BuybackAcceptedItem.objects.filter(active=True).only(
            "eve_type_id", "demand_status"
        )
    }
