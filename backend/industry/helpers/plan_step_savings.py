"""
Build-vs-buy saving for each intermediate step of a build plan.

For every intermediate job (advanced components, reactions, fuel blocks) the
planner compares two ways to get the units its parent jobs consume:

- buy: Jita sell for those units, plus alliance freight into the facility;
- build: that one job with every input bought (Jita sell + freight), plus its
  install cost, facility tax and SCC surcharge.

``saving_isk`` = buy − build. Each step is valued on its own, with its inputs
bought, so the saving of a reaction under a component is added on top of the
component's saving: ticking both saves roughly the sum.

Costs use the same price (industry Jita sell) and freight (alliance route)
as the planner's cost breakdown. The whole build cost counts against the
units consumed, so a reaction that makes more than the parent needs is not
credited for the surplus.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from eveuniverse.models import EveType

from industry.helpers.build_planner import BuildPlan, JobPlan
from industry.helpers.cost_breakdown import jita_sell_prices_by_type_id
from industry.helpers.freight_costs import (
    eve_type_volume_m3,
    estimate_freight_cost,
    find_inbound_freight_route,
)


@dataclass(frozen=True)
class StepSaving:
    type_id: int
    name: str
    # Units the parent jobs consume.
    quantity: int
    build_isk: int
    # None when the step has no Jita price to compare against.
    buy_isk: Optional[int]
    saving_isk: Optional[int]


class _CargoPricer:
    """Jita sell + inbound freight for cargoes into one facility."""

    def __init__(self, facility_key: str, type_ids: Iterable[int]):
        ids = sorted({int(tid) for tid in type_ids if tid})
        self.facility_key = facility_key
        self.prices: Dict[int, int] = jita_sell_prices_by_type_id(ids)
        self.volumes: Dict[int, float] = {
            int(tid): eve_type_volume_m3(eve_type)
            for tid, eve_type in EveType.objects.in_bulk(ids).items()
        }
        self.route = find_inbound_freight_route(facility_key)

    def delivered_isk(self, type_qtys: Sequence[Tuple[int, int]]) -> int:
        materials_isk = 0
        volume = 0.0
        for tid, qty in type_qtys:
            if qty <= 0:
                continue
            materials_isk += int(qty) * int(self.prices.get(int(tid), 0))
            volume += int(qty) * float(self.volumes.get(int(tid), 0.0))
        freight = estimate_freight_cost(
            facility_key=self.facility_key,
            volume_m3=volume,
            collateral_isk=materials_isk,
            route=self.route,
        )
        return materials_isk + int(freight.freight_isk)


def _job_install_isk(job: JobPlan) -> int:
    cost = job.job_cost
    return int(cost.gross_cost + cost.facility_tax_isk + cost.scc_tax_isk)


def _job_inputs(job: JobPlan) -> List[Tuple[int, int]]:
    merged: Dict[int, int] = defaultdict(int)
    for line in job.materials:
        merged[int(line.type_id)] += int(line.quantity)
    return list(merged.items())


def plan_step_savings(plan: BuildPlan) -> List[StepSaving]:
    """Saving for each intermediate job in ``plan``, by product name."""
    root_id = int(plan.product_type_id)
    steps = [job for job in plan.jobs if int(job.product_type_id) != root_id]
    if not steps:
        return []

    consumed: Dict[int, int] = defaultdict(int)
    for job in plan.jobs:
        for line in job.materials:
            consumed[int(line.type_id)] += int(line.quantity)

    type_ids = {int(job.product_type_id) for job in steps}
    for job in steps:
        type_ids.update(int(line.type_id) for line in job.materials)
    pricer = _CargoPricer(plan.facility_key, type_ids)

    savings: List[StepSaving] = []
    for job in sorted(steps, key=lambda row: row.product_name):
        type_id = int(job.product_type_id)
        quantity = consumed.get(type_id, 0)
        if quantity <= 0:
            continue
        build_isk = pricer.delivered_isk(_job_inputs(job)) + _job_install_isk(
            job
        )
        buy_isk: Optional[int] = None
        saving_isk: Optional[int] = None
        if pricer.prices.get(type_id, 0) > 0:
            buy_isk = pricer.delivered_isk([(type_id, quantity)])
            saving_isk = buy_isk - build_isk
        savings.append(
            StepSaving(
                type_id=type_id,
                name=job.product_name,
                quantity=quantity,
                build_isk=build_isk,
                buy_isk=buy_isk,
                saving_isk=saving_isk,
            )
        )
    return savings
