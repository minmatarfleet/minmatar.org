"""
EVE Online industry formulas for materials, time, and job installation cost.

Adapted from https://www.c4813.space/eve-online-industry-formula/ and EVE University.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple


def material_efficiency_total(
    blueprint_me: float,
    structure_role_me: float,
    rig_effective_me: float,
) -> float:
    """
    Total ME fraction applied to materials.

    1 - ME_total = (1 - bpME) * (1 - structureRole) * (1 - rigEffective)
    """
    return 1.0 - (
        (1.0 - blueprint_me)
        * (1.0 - structure_role_me)
        * (1.0 - rig_effective_me)
    )


def required_material_quantity(
    runs: int,
    base_quantity: int,
    me_total: float,
) -> int:
    """
    required = max(runs, ceil(round(runs * base * (1 - ME_total), 2)))

    Single-unit-per-run inputs (base_quantity == 1) stay at `runs`.
    """
    if runs <= 0:
        return 0
    if base_quantity <= 0:
        return 0
    if base_quantity == 1:
        return runs
    adjusted = round(runs * base_quantity * (1.0 - me_total), 2)
    return max(runs, math.ceil(adjusted))


def time_efficiency_multiplier(
    blueprint_te: float,
    structure_role_te: float,
    rig_effective_te: float,
    *,
    industry_level: int = 0,
    advanced_industry_level: int = 0,
    reaction_skill_level: int = 0,
    implant_te: float = 0.0,
    is_reaction: bool = False,
) -> float:
    """
    Product of all TE reduction factors (result multiplies base time).

    Manufacturing uses Industry (4%/level) and Advanced Industry (3%/level).
    Reactions use the Reactions skill (4%/level) instead.
    """
    mult = (
        (1.0 - blueprint_te)
        * (1.0 - structure_role_te)
        * (1.0 - rig_effective_te)
        * (1.0 - implant_te)
    )
    if is_reaction:
        mult *= 1.0 - reaction_skill_level * 0.04
    else:
        mult *= 1.0 - industry_level * 0.04
        mult *= 1.0 - advanced_industry_level * 0.03
    return mult


def job_duration_seconds(
    base_time_per_run: int,
    runs: int,
    te_multiplier: float,
) -> float:
    """Production time in seconds (may be fractional before display)."""
    if runs <= 0 or base_time_per_run <= 0:
        return 0.0
    return base_time_per_run * runs * te_multiplier


@dataclass(frozen=True)
class JobCostBreakdown:
    eiv: float
    gross_cost: int
    tax: int
    total: int
    system_cost_index: float
    structure_isk_bonus: float
    facility_tax: float
    scc_surcharge: float
    system_cost_bonus: float = 0.0
    facility_tax_isk: int = 0
    scc_tax_isk: int = 0


def estimated_item_value(
    base_materials: Sequence[Tuple[int, float]],
    runs: int,
) -> float:
    """
    EIV = sum(baseQty * adjusted_price) * runs

    base_materials: iterable of (base_quantity_per_run, adjusted_price).
    Uses ME0 / blueprint-base quantities, not ME-adjusted job inputs.
    """
    if runs <= 0:
        return 0.0
    total = 0.0
    for base_qty, adjusted_price in base_materials:
        total += base_qty * adjusted_price
    return total * runs


def job_installation_cost(
    eiv: float,
    system_cost_index: float,
    structure_isk_bonus: float = 0.0,
    facility_tax: float = 0.0,
    scc_surcharge: float = 0.04,
    system_cost_bonus: float = 0.0,
) -> JobCostBreakdown:
    """
    gross = floor(
        EIV * systemCostIndex * (1 - structureIskBonus) * (1 + systemCostBonus)
    )
    facility_tax_isk = floor(EIV * facilityTax)
    scc_tax_isk = floor(EIV * sccSurcharge)
    tax = facility_tax_isk + scc_tax_isk
    total = gross + tax

    system_cost_bonus is typically the FW facility-pricing bonus (e.g. -0.5).
    It applies only to the system-index gross; SCC / facility tax are unchanged.
    """
    if eiv <= 0 or system_cost_index < 0:
        return JobCostBreakdown(
            eiv=max(eiv, 0.0),
            gross_cost=0,
            tax=0,
            total=0,
            system_cost_index=system_cost_index,
            structure_isk_bonus=structure_isk_bonus,
            facility_tax=facility_tax,
            scc_surcharge=scc_surcharge,
            system_cost_bonus=system_cost_bonus,
            facility_tax_isk=0,
            scc_tax_isk=0,
        )
    gross = math.floor(
        eiv
        * system_cost_index
        * (1.0 - structure_isk_bonus)
        * (1.0 + system_cost_bonus)
    )
    # Facility tax and SCC are floored separately (EVE client behavior).
    facility_tax_isk = math.floor(eiv * facility_tax)
    scc_tax_isk = math.floor(eiv * scc_surcharge)
    tax = facility_tax_isk + scc_tax_isk
    return JobCostBreakdown(
        eiv=eiv,
        gross_cost=gross,
        tax=tax,
        total=gross + tax,
        system_cost_index=system_cost_index,
        structure_isk_bonus=structure_isk_bonus,
        facility_tax=facility_tax,
        scc_surcharge=scc_surcharge,
        system_cost_bonus=system_cost_bonus,
        facility_tax_isk=facility_tax_isk,
        scc_tax_isk=scc_tax_isk,
    )


def sum_job_costs(costs: Iterable[JobCostBreakdown]) -> int:
    return sum(c.total for c in costs)
