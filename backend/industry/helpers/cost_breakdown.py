"""
Aggregate build-plan costs: Jita material sell, job installation, taxes,
and freight (alliance route by default).

Prefer ``industry.helpers.plan_costing.plan_item_cost`` /
``cost_build_plan`` for new callers. ``build_plan_cost_breakdown`` remains
as a thin legacy adapter for tests and gradual migration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from eveonline.models import EveLocation
from eveuniverse.models import EveType

from industry.helpers.build_planner import BuildPlan
from industry.helpers.compressed_ore import CompressedOrePlan
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
    Industry “Jita sell”: lowest sell at price_baseline LocationPrice when
    present, else regional guide via get_prices_by_type_id.

    Prefer get_prices_by_type_id alone when you need the Forge history
    guide (buyback, LP store), not this hybrid.
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
    Estimated Jita value of materials produced by reprocessing compressed
    ore/ice.

    ``expected_minerals`` holds portion-aware ore/moon outputs;
    ``expected_ice_products`` holds ice refine outputs.
    """
    outputs: Dict[str, int] = dict(ore_plan.expected_minerals)
    for name, qty in ore_plan.expected_ice_products.items():
        outputs[name] = outputs.get(name, 0) + int(qty)
    if not ore_plan.includes_compressed_ore or not outputs:
        return 0
    if prices_by_name is None:
        prices_by_name = _prices_by_name(outputs.keys())
    return materials_jita_sell_isk_from_named(
        outputs, prices_by_name=prices_by_name
    )


# Circular import: plan_costing imports material helpers from this module;
# this adapter calls cost_build_plan. Keep the import local.
from industry.helpers.plan_costing import (  # noqa: E402  # pylint: disable=wrong-import-position,ungrouped-imports
    FreightOptions,
    cost_build_plan,
)


def build_plan_cost_breakdown(
    plan: BuildPlan,
    *,
    compressed_ore: Optional[CompressedOrePlan] = None,
    navy_bpc_isk: int = 0,
) -> PlanCostBreakdown:
    """
    Full build cost with alliance inbound freight (legacy adapter).

    New code should use ``industry.helpers.plan_costing.cost_build_plan``.
    """
    item = cost_build_plan(
        plan,
        compressed_ore=compressed_ore,
        navy_bpc_isk=navy_bpc_isk,
        input_freight=FreightOptions.alliance_default(),
        include_line_items=True,
    )
    freight = item.input_freight
    return PlanCostBreakdown(
        materials_jita_sell_isk=item.materials_jita_sell_isk,
        manufacturing_job_costs_isk=item.manufacturing_job_costs_isk,
        reaction_job_costs_isk=item.reaction_job_costs_isk,
        total_job_costs_isk=item.total_job_costs_isk,
        facility_tax_isk=item.facility_tax_isk,
        scc_tax_isk=item.scc_tax_isk,
        reprocessing_tax_isk=item.reprocessing_tax_isk,
        taxes_isk=item.taxes_isk,
        freight_isk=freight.isk,
        freight_volume_m3=freight.volume_m3,
        freight_billable_m3=freight.billable_m3,
        freight_route_id=freight.route_id,
        freight_route_label=freight.route_label,
        navy_bpc_isk=item.navy_bpc_isk,
        grand_total_isk=item.grand_total_isk,
        per_unit_isk=item.per_unit_isk,
        output_quantity=item.output_quantity,
        line_items=[
            CostLineItem(
                key=row.key, label=row.label, amount_isk=row.amount_isk
            )
            for row in item.line_items
        ],
    )
