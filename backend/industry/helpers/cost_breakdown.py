"""
Aggregate build-plan costs: Jita material sell, job installation, taxes,
and alliance freight (when a hub→facility route exists).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from eveonline.models import EveLocation
from eveuniverse.models import EveType

from industry.helpers.build_planner import BuildPlan
from industry.helpers.compressed_ore import CompressedOrePlan
from industry.helpers.freight_costs import estimate_plan_freight
from industry.helpers.type_breakdown import ACTIVITY_REACTION
from market.helpers.pricing import get_prices_by_type_id
from market.models import EveMarketItemLocationPrice


@dataclass(frozen=True)
class CostLineItem:
    key: str
    label: str
    amount_isk: int


@dataclass
class PlanCostBreakdown:
    materials_jita_sell_isk: int = 0
    manufacturing_job_costs_isk: int = 0
    reaction_job_costs_isk: int = 0
    total_job_costs_isk: int = 0
    facility_tax_isk: int = 0
    scc_tax_isk: int = 0
    reprocessing_tax_isk: int = 0
    taxes_isk: int = 0
    freight_isk: int = 0
    freight_volume_m3: float = 0.0
    freight_billable_m3: int = 0
    freight_route_id: Optional[int] = None
    freight_route_label: Optional[str] = None
    navy_bpc_isk: int = 0
    grand_total_isk: int = 0
    per_unit_isk: float = 0.0
    output_quantity: int = 1
    line_items: List[CostLineItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "materials_jita_sell_isk": self.materials_jita_sell_isk,
            "manufacturing_job_costs_isk": self.manufacturing_job_costs_isk,
            "reaction_job_costs_isk": self.reaction_job_costs_isk,
            "total_job_costs_isk": self.total_job_costs_isk,
            "facility_tax_isk": self.facility_tax_isk,
            "scc_tax_isk": self.scc_tax_isk,
            "reprocessing_tax_isk": self.reprocessing_tax_isk,
            "taxes_isk": self.taxes_isk,
            "freight_isk": self.freight_isk,
            "freight_volume_m3": self.freight_volume_m3,
            "freight_billable_m3": self.freight_billable_m3,
            "freight_route_id": self.freight_route_id,
            "freight_route_label": self.freight_route_label,
            "navy_bpc_isk": self.navy_bpc_isk,
            "grand_total_isk": self.grand_total_isk,
            "per_unit_isk": self.per_unit_isk,
            "output_quantity": self.output_quantity,
            "line_items": [
                {
                    "key": item.key,
                    "label": item.label,
                    "amount_isk": item.amount_isk,
                }
                for item in self.line_items
            ],
        }


def jita_sell_prices_by_type_id(type_ids: Sequence[int]) -> Dict[int, int]:
    """
    Lowest sell at the price_baseline location when available, else Jita-region
    history / EveMarketPrice via ``get_prices_by_type_id``.
    """
    unique = list({int(tid) for tid in type_ids if tid})
    if not unique:
        return {}

    prices: Dict[int, int] = {}
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline is not None:
        for tid, sell in EveMarketItemLocationPrice.objects.filter(
            location=baseline, item_id__in=unique
        ).values_list("item_id", "sell_price"):
            if sell is not None:
                prices[int(tid)] = int(sell)

    missing = [tid for tid in unique if tid not in prices]
    if missing:
        prices.update(get_prices_by_type_id(missing))
    return prices


def _prices_by_name(names: Iterable[str]) -> Dict[str, int]:
    unique = sorted({n for n in names if n})
    if not unique:
        return {}
    type_rows = EveType.objects.filter(name__in=unique).values_list(
        "id", "name"
    )
    id_to_name = {int(tid): name for tid, name in type_rows}
    prices = jita_sell_prices_by_type_id(list(id_to_name.keys()))
    return {
        id_to_name[tid]: int(price)
        for tid, price in prices.items()
        if tid in id_to_name
    }


def materials_jita_sell_isk_from_type_qtys(
    type_qtys: Sequence[Tuple[int, int]],
    *,
    prices_by_type: Optional[Dict[int, int]] = None,
) -> int:
    """Sum qty × Jita-baseline sell for (type_id, qty) rows."""
    if not type_qtys:
        return 0
    if prices_by_type is None:
        prices_by_type = jita_sell_prices_by_type_id(
            [tid for tid, _ in type_qtys]
        )
    total = 0
    for tid, qty in type_qtys:
        if qty <= 0:
            continue
        total += int(qty) * int(prices_by_type.get(int(tid), 0))
    return total


def materials_jita_sell_isk_from_named(
    named_qtys: Dict[str, int],
    *,
    prices_by_name: Optional[Dict[str, int]] = None,
) -> int:
    """Sum qty × Jita-baseline sell for name→qty maps (compressed imports)."""
    if not named_qtys:
        return 0
    if prices_by_name is None:
        prices_by_name = _prices_by_name(named_qtys.keys())
    total = 0
    for name, qty in named_qtys.items():
        if qty <= 0:
            continue
        total += int(qty) * int(prices_by_name.get(name, 0))
    return total


def reprocessing_output_value_isk(
    ore_plan: CompressedOrePlan,
    *,
    prices_by_name: Optional[Dict[str, int]] = None,
) -> int:
    """
    Estimated Jita value of materials produced by reprocessing compressed ore.

    ``expected_minerals`` holds portion-aware reprocess outputs (minerals and
    any PI P0 from moon ore).
    """
    if not ore_plan.includes_compressed_ore or not ore_plan.expected_minerals:
        return 0
    if prices_by_name is None:
        prices_by_name = _prices_by_name(ore_plan.expected_minerals.keys())
    return materials_jita_sell_isk_from_named(
        ore_plan.expected_minerals, prices_by_name=prices_by_name
    )


def build_plan_cost_breakdown(
    plan: BuildPlan,
    *,
    compressed_ore: Optional[CompressedOrePlan] = None,
    navy_bpc_isk: int = 0,
) -> PlanCostBreakdown:
    """
    Full build cost:

    materials (Jita sell) + job installation gross (system cost index × EIV,
    after structure/FW role bonuses) + facility tax + SCC (both on EIV from
    ESI adjusted prices at ME0) + reprocessing tax (when compressed ore is used)
    + alliance freight (hub→facility) when a priced route exists
    + navy BPC LP cost when provided.
    """
    mfg_gross = 0
    rxn_gross = 0
    facility_tax_isk = 0
    scc_tax_isk = 0
    for job in plan.jobs:
        facility_tax_isk += job.job_cost.facility_tax_isk
        scc_tax_isk += job.job_cost.scc_tax_isk
        if job.activity_id == ACTIVITY_REACTION:
            rxn_gross += job.job_cost.gross_cost
        else:
            mfg_gross += job.job_cost.gross_cost

    total_job_costs = mfg_gross + rxn_gross
    navy_bpc_isk = max(int(navy_bpc_isk), 0)

    if compressed_ore is not None:
        import_map = dict(compressed_ore.import_lines())
        names = set(import_map) | set(compressed_ore.expected_minerals)
        prices_by_name = _prices_by_name(names)
        materials_isk = materials_jita_sell_isk_from_named(
            import_map, prices_by_name=prices_by_name
        )
        output_value = reprocessing_output_value_isk(
            compressed_ore, prices_by_name=prices_by_name
        )
        reprocessing_tax_isk = compressed_ore.tax_isk(float(output_value))
        freight = estimate_plan_freight(
            facility_key=plan.facility_key,
            named_qtys=import_map,
            collateral_isk=materials_isk,
        )
    else:
        type_qtys = [
            (tid, qty) for tid, (_, qty) in plan.leaf_materials.items()
        ]
        materials_isk = materials_jita_sell_isk_from_type_qtys(type_qtys)
        reprocessing_tax_isk = 0
        freight = estimate_plan_freight(
            facility_key=plan.facility_key,
            type_qtys=type_qtys,
            collateral_isk=materials_isk,
        )

    taxes_isk = facility_tax_isk + scc_tax_isk + reprocessing_tax_isk
    freight_isk = int(freight.freight_isk)
    grand_total = (
        materials_isk
        + total_job_costs
        + taxes_isk
        + freight_isk
        + navy_bpc_isk
    )
    output_qty = max(int(plan.quantity), 1)
    per_unit = grand_total / output_qty

    freight_label = "Freight"
    if freight.route_label:
        freight_label = f"Freight ({freight.route_label})"

    line_items: List[CostLineItem] = [
        CostLineItem(
            "materials_jita_sell",
            "Materials",
            materials_isk,
        ),
        CostLineItem(
            "manufacturing_job_costs",
            "Manufacturing job install",
            mfg_gross,
        ),
        CostLineItem(
            "reaction_job_costs",
            "Reaction job install",
            rxn_gross,
        ),
        CostLineItem(
            "facility_tax",
            "Facility tax",
            facility_tax_isk,
        ),
        CostLineItem(
            "scc_tax",
            "SCC surcharge",
            scc_tax_isk,
        ),
    ]
    # Only when compressed ore is in use (show even if tax rounds to 0).
    if compressed_ore is not None:
        line_items.append(
            CostLineItem(
                "reprocessing_tax",
                "Reprocessing tax",
                reprocessing_tax_isk,
            )
        )
    # Only surface freight when a priced route matched (omit invented rates).
    if freight.has_route:
        line_items.append(CostLineItem("freight", freight_label, freight_isk))
    if navy_bpc_isk > 0:
        line_items.append(
            CostLineItem("navy_bpc_lp", "Navy BPC (LP)", navy_bpc_isk)
        )

    return PlanCostBreakdown(
        materials_jita_sell_isk=materials_isk,
        manufacturing_job_costs_isk=mfg_gross,
        reaction_job_costs_isk=rxn_gross,
        total_job_costs_isk=total_job_costs,
        facility_tax_isk=facility_tax_isk,
        scc_tax_isk=scc_tax_isk,
        reprocessing_tax_isk=reprocessing_tax_isk,
        taxes_isk=taxes_isk,
        freight_isk=freight_isk,
        freight_volume_m3=float(freight.volume_m3),
        freight_billable_m3=int(freight.billable_m3),
        freight_route_id=freight.route_id,
        freight_route_label=freight.route_label,
        navy_bpc_isk=navy_bpc_isk,
        grand_total_isk=grand_total,
        per_unit_isk=per_unit,
        output_quantity=output_qty,
        line_items=line_items,
    )
