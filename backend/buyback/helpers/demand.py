"""Supply-chain demand set for buyback rates (recent order import leaves)."""

from __future__ import annotations

from eveonline.helpers.universe import type_ids_by_name

from buyback.models import BuybackAcceptedItem
from industry.helpers.compressed_ore import ore_materials_per_portion

RATE_REASON_SUPPLY_CHAIN = "supply_chain_import"
RATE_REASON_SURPLUS = "accepted_surplus"


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
    return type_ids_by_name(mineral_names)


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
