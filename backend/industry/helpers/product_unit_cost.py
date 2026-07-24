"""
Per-product unit build cost at a facility (Amamake compressed ore + navy BPC).

Shared by guide-order export and open-orders profit-summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from eveuniverse.models import EveType

from industry.helpers.blueprint_efficiency import (
    default_blueprint_me_te_percent,
    is_faction_navy_hull,
)
from industry.helpers.build_planner import plan_build
from industry.helpers.compressed_ore import build_compressed_ore_plan
from industry.helpers.cost_breakdown import (
    build_plan_cost_breakdown,
    jita_sell_prices_by_type_id,
)
from industry.helpers.facility_profiles import get_facility_reprocessing_tax
from industry.helpers.loyalty_store import (
    get_offer_for_blueprint_type,
    navy_bpc_cost_for_plan,
    resolve_isk_per_lp,
)
from industry.helpers.reprocessing_skills import resolve_refine_rate
from industry.helpers.type_breakdown import get_blueprint_or_reaction_type_id

FACILITY_KEY = "amamake"

# Talwar FI: local SDE may lack BP; BOM matches other navy destroyers.
TALWAR_FI_TYPE_ID = 91858
TALWAR_FI_BPC_TYPE_ID = 91862
TALWAR_FI_BOM_PROXY_TYPE_ID = 73796  # Catalyst Navy Issue


@dataclass(frozen=True)
class ProductUnitCost:
    type_id: int
    name: str
    kind: str  # "Navy" | "T1"
    cost_per: int
    jita_sell: int
    profit_per: int
    isk_per_lp: Optional[float]
    note: Optional[str] = None


def bom_and_bpc_overrides(
    type_id: int,
) -> Tuple[int, Optional[int], Optional[str]]:
    """Return (bom_type_id, bpc_type_id, note) for known SDE gaps."""
    if int(type_id) == TALWAR_FI_TYPE_ID:
        return (
            TALWAR_FI_BOM_PROXY_TYPE_ID,
            TALWAR_FI_BPC_TYPE_ID,
            "BOM proxied (identical navy destroyer recipe)",
        )
    return int(type_id), None, None


def plan_product(
    product_type_id: int,
    *,
    quantity: int = 1,
    facility: str = FACILITY_KEY,
):
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
    breakdown = build_plan_cost_breakdown(
        plan,
        compressed_ore=ore_plan,
        navy_bpc_isk=navy_bpc_isk,
    )
    return int(breakdown.grand_total_isk)


def uncompressed_total_isk(plan, *, navy_bpc_isk: int) -> int:
    breakdown = build_plan_cost_breakdown(
        plan,
        compressed_ore=None,
        navy_bpc_isk=navy_bpc_isk,
    )
    return int(breakdown.grand_total_isk)


def navy_bpc_isk_for_product(
    *,
    product_type_id: int,
    bpc_type_id: Optional[int],
    quantity: int,
    isk_per_lp: Optional[float],
) -> Tuple[int, Optional[float]]:
    """Return (navy_bpc_isk, effective_isk_per_lp)."""
    blueprint_type_id = bpc_type_id
    if blueprint_type_id is None:
        eve_type = EveType.objects.filter(id=product_type_id).first()
        if eve_type is None or not is_faction_navy_hull(eve_type):
            return 0, None
        blueprint_type_id = get_blueprint_or_reaction_type_id(eve_type)

    if blueprint_type_id is None:
        return 0, None

    offer = get_offer_for_blueprint_type(int(blueprint_type_id))
    corp_id = offer.corporation_id if offer is not None else None
    rate = resolve_isk_per_lp(requested=isk_per_lp, corporation_id=corp_id)
    if rate is None:
        return 0, None

    cost = navy_bpc_cost_for_plan(
        int(blueprint_type_id), quantity, float(rate)
    )
    if cost is None:
        return 0, float(rate)
    return int(cost.total_isk), float(rate)


def resolve_production_isk_per_lp(
    product_type_id: int,
    *,
    bpc_type_id: Optional[int] = None,
) -> Optional[float]:
    blueprint_type_id = bpc_type_id
    if blueprint_type_id is None:
        eve_type = EveType.objects.filter(id=product_type_id).first()
        if eve_type is None:
            return None
        blueprint_type_id = get_blueprint_or_reaction_type_id(eve_type)
    if blueprint_type_id is None:
        return None
    offer = get_offer_for_blueprint_type(int(blueprint_type_id))
    corp_id = offer.corporation_id if offer is not None else None
    return resolve_isk_per_lp(requested=None, corporation_id=corp_id)


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

    Plans a lot of ``quantity`` (e.g. max claim size) then returns per-unit cost,
    so compressed-ore shopping matches how industrialists actually claim.

    When ``use_production_lp`` is True and ``isk_per_lp`` is None, uses
    IndustryLoyaltyPoint defaults for the product's LP corp.
    """
    type_id = int(type_id)
    batch = max(int(quantity), 1)
    eve_type = EveType.objects.filter(id=type_id).first()
    if eve_type is None:
        raise ValueError(f"Unknown product_type_id {type_id}")

    bom_type_id, bpc_override, note = bom_and_bpc_overrides(type_id)
    is_navy = is_faction_navy_hull(eve_type)
    kind = "Navy" if is_navy else "T1"

    requested_lp: Optional[float] = None
    if is_navy:
        if isk_per_lp is not None and float(isk_per_lp) > 0:
            requested_lp = float(isk_per_lp)
        elif use_production_lp:
            requested_lp = resolve_production_isk_per_lp(
                type_id, bpc_type_id=bpc_override
            )

    navy_isk, effective_lp = navy_bpc_isk_for_product(
        product_type_id=type_id,
        bpc_type_id=bpc_override,
        quantity=batch,
        isk_per_lp=requested_lp,
    )

    plan = plan_product(bom_type_id, quantity=batch, facility=facility)
    if compressed:
        batch_total = compressed_total_isk(
            plan, facility=facility, navy_bpc_isk=navy_isk
        )
    else:
        batch_total = uncompressed_total_isk(plan, navy_bpc_isk=navy_isk)
    cost_per = int(round(batch_total / batch))

    prices = sell_prices or jita_sell_prices_by_type_id([type_id])
    jita_sell = int(prices.get(type_id) or 0)
    profit_per = jita_sell - cost_per

    return ProductUnitCost(
        type_id=type_id,
        name=eve_type.name or str(type_id),
        kind=kind,
        cost_per=cost_per,
        jita_sell=jita_sell,
        profit_per=profit_per,
        isk_per_lp=effective_lp if is_navy else None,
        note=note,
    )
