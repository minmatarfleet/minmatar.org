"""
EVE Online industry formulas for materials, time, and job installation cost.

Adapted from https://www.c4813.space/eve-online-industry-formula/ and EVE University.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence, Tuple


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


def job_run_batches(
    total_runs: int, max_runs_per_job: int | None
) -> list[int]:
    """Split `total_runs` into blueprint-copy sized jobs.

    ``None``, ``0``, or a cap at least as large as ``total_runs`` is one job.
    A shorter last job keeps the leftover runs.
    """
    if total_runs <= 0:
        return []
    if (
        max_runs_per_job is None
        or max_runs_per_job <= 0
        or max_runs_per_job >= total_runs
    ):
        return [total_runs]
    full, remainder = divmod(total_runs, max_runs_per_job)
    batches = [max_runs_per_job] * full
    if remainder:
        batches.append(remainder)
    return batches


def batched_material_quantity(
    total_runs: int,
    base_quantity: int,
    me_total: float,
    max_runs_per_job: int | None = None,
) -> int:
    """Materials for several jobs, each ceiled on its own.

    One 500-run job and fifty 10-run jobs do not use the same quantity:
    EVE rounds each job, then the jobs are added.
    """
    return sum(
        required_material_quantity(runs, base_quantity, me_total)
        for runs in job_run_batches(total_runs, max_runs_per_job)
    )


def sum_job_costs(parts: Sequence[JobCostBreakdown]) -> JobCostBreakdown:
    """Add per-job install costs. Rates are taken from the first part."""
    if not parts:
        raise ValueError("sum_job_costs requires at least one job")
    first = parts[0]
    return JobCostBreakdown(
        eiv=sum(part.eiv for part in parts),
        gross_cost=sum(part.gross_cost for part in parts),
        tax=sum(part.tax for part in parts),
        total=sum(part.total for part in parts),
        system_cost_index=first.system_cost_index,
        structure_isk_bonus=first.structure_isk_bonus,
        facility_tax=first.facility_tax,
        scc_surcharge=first.scc_surcharge,
        system_cost_bonus=first.system_cost_bonus,
        facility_tax_isk=sum(part.facility_tax_isk for part in parts),
        scc_tax_isk=sum(part.scc_tax_isk for part in parts),
    )


def batched_job_installation_cost(
    total_eiv: float,
    total_runs: int,
    max_runs_per_job: int | None,
    system_cost_index: float,
    structure_isk_bonus: float = 0.0,
    facility_tax: float = 0.0,
    scc_surcharge: float = 0.04,
    system_cost_bonus: float = 0.0,
) -> JobCostBreakdown:
    """Install cost floored per job, then summed.

    A single job uses ``total_eiv`` unchanged so the one-job path stays
    identical. Extra jobs split EIV by runs; the last job gets the remainder.
    """
    batches = job_run_batches(total_runs, max_runs_per_job)
    kwargs = {
        "system_cost_index": system_cost_index,
        "structure_isk_bonus": structure_isk_bonus,
        "facility_tax": facility_tax,
        "scc_surcharge": scc_surcharge,
        "system_cost_bonus": system_cost_bonus,
    }
    if len(batches) <= 1:
        return job_installation_cost(total_eiv, **kwargs)
    eiv_per_run = total_eiv / total_runs
    parts: list[JobCostBreakdown] = []
    allocated = 0.0
    for index, runs in enumerate(batches):
        if index == len(batches) - 1:
            part_eiv = total_eiv - allocated
        else:
            part_eiv = eiv_per_run * runs
            allocated += part_eiv
        parts.append(job_installation_cost(part_eiv, **kwargs))
    return sum_job_costs(parts)


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
    CCP job install cost (Steve Ronuken / in-game Industry UI):

    gross = floor(
        EIV * systemCostIndex * (1 - structureIskBonus) * (1 + systemCostBonus)
    )
    facility_tax_isk = floor(EIV * facilityTax)
    scc_tax_isk = floor(EIV * sccSurcharge)
    tax = facility_tax_isk + scc_tax_isk
    total = gross + tax

    EIV uses ME0 material quantities × ESI adjusted_price (not Jita sell/buy).
    Structure role bonus and system_cost_bonus (e.g. FW −50%) apply only to the
    cost-index gross; facility tax and SCC are always on EIV.
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
