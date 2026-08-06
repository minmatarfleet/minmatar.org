"""
Per-product unit build cost at a facility (Amamake compressed ore + navy BPC).

Thin compatibility wrapper over ``industry.helpers.plan_costing.plan_item_cost``.
Prefer calling ``plan_item_cost`` directly for new code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from eveuniverse.models import EveType

from industry.helpers.blueprint_efficiency import (
    default_blueprint_me_te_percent,
)
from industry.helpers.build_planner import plan_build
from industry.helpers.compressed_ore import build_compressed_ore_plan
from industry.helpers.facility_profiles import get_facility_reprocessing_tax
from industry.helpers.plan_costing import (
    DEFAULT_FACILITY_KEY as FACILITY_KEY,
    TALWAR_FI_BOM_PROXY_TYPE_ID,
    TALWAR_FI_BPC_TYPE_ID,
    TALWAR_FI_TYPE_ID,
    FreightOptions,
    PlanCostOptions,
    bom_and_bpc_overrides,
    cost_build_plan,
    navy_bpc_isk_for_product,
    plan_item_cost,
    resolve_production_isk_per_lp,
)
from industry.helpers.reprocessing_skills import resolve_refine_rate

# Re-export constants used by other modules / tests.
__all__ = [
    "FACILITY_KEY",
    "TALWAR_FI_TYPE_ID",
    "TALWAR_FI_BPC_TYPE_ID",
    "TALWAR_FI_BOM_PROXY_TYPE_ID",
    "ProductUnitCost",
    "bom_and_bpc_overrides",
    "navy_bpc_isk_for_product",
    "resolve_production_isk_per_lp",
    "plan_product",
    "compressed_total_isk",
    "uncompressed_total_isk",
    "plan_product_unit_cost",
]


@dataclass(frozen=True)
class ProductUnitCost:
    type_id: int
    name: str
    kind: str  # "Navy" | "T1"
    cost_per: int
    # Build cost excluding navy BPC LP/ISK (materials, jobs, taxes, freight).
    manufacturing_cost_per: int
    jita_sell: int
    profit_per: int
    isk_per_lp: Optional[float]
    note: Optional[str] = None


def plan_product(
    product_type_id: int,
    *,
    quantity: int = 1,
    facility: str = FACILITY_KEY,
):
    """Legacy helper — prefer ``plan_item_cost``."""
    eve_type = EveType.objects.filter(id=product_type_id).first()
    if eve_type is None:
        raise ValueError(f"Unknown product_type_id {product_type_id}")
    me_pct, te_pct = default_blueprint_me_te_percent(eve_type)
    return plan_build(
        eve_type,
        quantity=quantity,
        blueprint_me=me_pct / 100.0,
        blueprint_te=te_pct / 100.0,
        facility=facility,
    )


def compressed_total_isk(plan, *, facility: str, navy_bpc_isk: int) -> int:
    """Legacy helper — prefer ``cost_build_plan``."""
    refine = resolve_refine_rate(
        facility,
        character=None,
        use_reprocessing_implants=False,
    )[0]
    materials = {name: qty for _, (name, qty) in plan.leaf_materials.items()}
    ore_plan = build_compressed_ore_plan(
        materials,
        refine_rate=refine,
        reprocessing_tax=get_facility_reprocessing_tax(facility),
    )
    item = cost_build_plan(
        plan,
        compressed_ore=ore_plan,
        navy_bpc_isk=navy_bpc_isk,
        input_freight=FreightOptions.alliance_default(),
    )
    return int(item.grand_total_isk)


def uncompressed_total_isk(plan, *, navy_bpc_isk: int) -> int:
    """Legacy helper — prefer ``cost_build_plan``."""
    item = cost_build_plan(
        plan,
        compressed_ore=None,
        navy_bpc_isk=navy_bpc_isk,
        input_freight=FreightOptions.alliance_default(),
    )
    return int(item.grand_total_isk)


def plan_product_unit_cost(
    type_id: int,
    *,
    quantity: int = 1,
    facility: str = FACILITY_KEY,
    compressed: bool = True,
    isk_per_lp: Optional[float] = None,
    use_production_lp: bool = True,
    sell_prices: Optional[Dict[int, int]] = None,
) -> ProductUnitCost:
    """
    Unit build cost + Jita sell for one product.

    Wrapper around ``plan_item_cost`` with alliance inbound freight.
    """
    item = plan_item_cost(
        int(type_id),
        PlanCostOptions.planner_defaults(
            facility=facility,
            quantity=max(int(quantity), 1),
            compressed=compressed,
            isk_per_lp=isk_per_lp,
            use_production_lp=use_production_lp,
            include_navy_bpc=True,
            include_line_items=False,
        ),
        sell_prices=sell_prices,
    )
    return ProductUnitCost(
        type_id=item.type_id,
        name=item.name,
        kind=item.kind or "T1",
        cost_per=item.cost_per_isk,
        manufacturing_cost_per=item.manufacturing_cost_per_isk,
        jita_sell=item.jita_sell_isk,
        profit_per=item.profit_per_isk,
        isk_per_lp=item.isk_per_lp,
        note=item.note,
    )
