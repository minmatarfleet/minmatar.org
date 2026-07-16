"""
Full manufacture + reaction job tree planner for alliance freeports.

Expands a product (default Typhoon) into explicit jobs with facility ME/TE,
ME-adjusted materials, TE-adjusted durations, and EIV-based installation costs.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from eveuniverse.models import (
    EveIndustryActivityDuration,
    EveIndustryActivityMaterial,
    EveIndustryActivityProduct,
    EveMarketPrice,
    EveType,
)

from eveonline.client import esi_provider
from industry.helpers.facility_profiles import (
    AMAMAKE_SYSTEM_ID,
    FacilityBonuses,
    JobClass,
    get_facility_profile,
    get_facility_system_id,
)
from industry.helpers.industry_formulas import (
    JobCostBreakdown,
    estimated_item_value,
    job_duration_seconds,
    job_installation_cost,
    material_efficiency_total,
    required_material_quantity,
    time_efficiency_multiplier,
)
from industry.helpers.type_breakdown import (
    ACTIVITY_MANUFACTURING,
    ACTIVITY_REACTION,
    get_blueprint_or_reaction_type_id,
)

logger = logging.getLogger(__name__)

DEFAULT_PRODUCT_TYPE_ID = 644  # Typhoon

# Eve group / category hints for job classification
CATEGORY_SHIP = 6
GROUP_CONSTRUCTION_COMPONENTS = 334
GROUP_FUEL_BLOCK = 1136
# Composite / hybrid / biochemical reaction intermediates
GROUP_COMPOSITE = 429
GROUP_HYBRID_POLYMERS = 974
GROUP_BIOCHEMICAL = 712


class JobBucket(str, Enum):
    END_PRODUCT = "end_products"
    ADVANCED_COMPONENTS = "advanced_components"
    FIRST_STAGE_REACTIONS = "first_stage_reactions"
    SECOND_STAGE_REACTIONS = "second_stage_reactions"
    OTHER = "other"


@dataclass
class Recipe:
    blueprint_type_id: int
    activity_id: int
    product_type_id: int
    product_name: str
    product_quantity: int
    base_time: int
    materials: List[Tuple[int, str, int]]  # type_id, name, qty_per_run


@dataclass
class MaterialLine:
    type_id: int
    name: str
    quantity: int
    base_quantity_per_run: int


@dataclass
class JobPlan:
    product_type_id: int
    product_name: str
    activity_id: int
    job_class: JobClass
    bucket: JobBucket
    runs: int
    facility_name: str
    blueprint_me: float
    blueprint_te: float
    me_total: float
    te_multiplier: float
    materials: List[MaterialLine]
    duration_seconds: float
    job_cost: JobCostBreakdown
    eiv: float


@dataclass
class BuildPlan:
    product_type_id: int
    product_name: str
    quantity: int
    blueprint_me: float
    blueprint_te: float
    facility_key: str
    system_id: int
    manufacturing_index: float
    reaction_index: float
    indices_from_esi: bool = True
    jobs: List[JobPlan] = field(default_factory=list)
    leaf_materials: Dict[int, Tuple[str, int]] = field(default_factory=dict)

    @property
    def total_duration_seconds(self) -> float:
        return sum(j.duration_seconds for j in self.jobs)

    @property
    def total_job_cost_isk(self) -> int:
        return sum(j.job_cost.total for j in self.jobs)

    def jobs_by_bucket(self) -> Dict[JobBucket, List[JobPlan]]:
        out: Dict[JobBucket, List[JobPlan]] = {b: [] for b in JobBucket}
        for job in self.jobs:
            out[job.bucket].append(job)
        return out

    def bucket_duration_seconds(self) -> Dict[JobBucket, float]:
        return {
            bucket: sum(j.duration_seconds for j in jobs)
            for bucket, jobs in self.jobs_by_bucket().items()
        }


@dataclass
class SkillSettings:
    industry_level: int = 5
    advanced_industry_level: int = 5
    reaction_skill_level: int = 5
    implant_te: float = 0.0


def resolve_product(name_or_id: str) -> EveType:
    """Resolve a product by type ID or exact/partial name."""
    text = name_or_id.strip()
    if text.isdigit():
        eve_type = EveType.objects.filter(id=int(text)).first()
        if eve_type is None:
            raise ValueError(f"Unknown type id {text}")
        return eve_type
    qs = EveType.objects.filter(name__iexact=text, published=True)
    if qs.count() == 1:
        return qs.get()
    qs = EveType.objects.filter(name__icontains=text, published=True)
    if qs.count() == 1:
        return qs.get()
    if qs.exists():
        names = ", ".join(qs.values_list("name", flat=True)[:8])
        raise ValueError(f"Ambiguous product {text!r}. Matches: {names}")
    raise ValueError(f"Unknown product {text!r}")


def _get_recipe(product_type_id: int) -> Optional[Recipe]:
    product = EveType.objects.filter(id=product_type_id).first()
    if product is None:
        return None
    # Ensures industry activity rows are loaded from SDE when available.
    get_blueprint_or_reaction_type_id(product)

    products = list(
        EveIndustryActivityProduct.objects.filter(
            product_eve_type_id=product_type_id,
            activity_id__in=(ACTIVITY_MANUFACTURING, ACTIVITY_REACTION),
        )
    )
    if not products:
        return None

    manuf = [p for p in products if p.activity_id == ACTIVITY_MANUFACTURING]
    chosen = manuf[0] if manuf else products[0]

    duration = (
        EveIndustryActivityDuration.objects.filter(
            eve_type_id=chosen.eve_type_id,
            activity_id=chosen.activity_id,
        )
        .values_list("time", flat=True)
        .first()
    )
    if duration is None:
        duration = 0

    mats = list(
        EveIndustryActivityMaterial.objects.filter(
            eve_type_id=chosen.eve_type_id,
            activity_id=chosen.activity_id,
        ).select_related("material_eve_type")
    )
    materials = [
        (m.material_eve_type_id, m.material_eve_type.name, m.quantity)
        for m in mats
    ]
    return Recipe(
        blueprint_type_id=chosen.eve_type_id,
        activity_id=chosen.activity_id,
        product_type_id=product_type_id,
        product_name=product.name,
        product_quantity=chosen.quantity or 1,
        base_time=int(duration),
        materials=materials,
    )


def _classify_job_class(recipe: Recipe, root_type_id: int) -> JobClass:
    if recipe.activity_id == ACTIVITY_REACTION:
        return JobClass.REACTION
    if recipe.product_type_id == root_type_id:
        return JobClass.SHIP_MANUFACTURING
    eve_type = (
        EveType.objects.select_related("eve_group", "eve_group__eve_category")
        .filter(id=recipe.product_type_id)
        .first()
    )
    if eve_type is not None and eve_type.eve_group is not None:
        category_id = (
            eve_type.eve_group.eve_category_id
            if eve_type.eve_group.eve_category_id
            else None
        )
        if category_id == CATEGORY_SHIP:
            return JobClass.SHIP_MANUFACTURING
    return JobClass.COMPONENT_MANUFACTURING


def _is_advanced_component(type_id: int) -> bool:
    eve_type = (
        EveType.objects.filter(id=type_id).select_related("eve_group").first()
    )
    if eve_type is None or eve_type.eve_group_id is None:
        return False
    return eve_type.eve_group_id == GROUP_CONSTRUCTION_COMPONENTS


def fetch_system_cost_indices(
    system_id: int = AMAMAKE_SYSTEM_ID,
) -> Tuple[float, float]:
    """
    Return live (manufacturing_index, reaction_index) for a solar system via ESI.

    Index values are fractions (e.g. 0.1238 for 12.38%).
    """
    try:
        rows = esi_provider.client.Industry.get_industry_systems().results()
    except Exception as exc:
        raise ValueError(
            f"Failed to fetch ESI industry cost indices: {exc}"
        ) from exc

    for row in rows:
        if int(row.get("solar_system_id", 0)) != int(system_id):
            continue
        manufacturing = 0.0
        reaction = 0.0
        for entry in row.get("cost_indices", []):
            activity = entry.get("activity")
            cost = float(entry.get("cost_index", 0.0))
            if activity == "manufacturing":
                manufacturing = cost
            elif activity == "reaction":
                reaction = cost
        logger.info(
            "Live ESI cost indices for system %s: manufacturing=%.6f reaction=%.6f",
            system_id,
            manufacturing,
            reaction,
        )
        return manufacturing, reaction
    raise ValueError(f"No industry cost indices for system {system_id}")


def resolve_cost_indices(
    facility: str,
    *,
    manufacturing_index: Optional[float] = None,
    reaction_index: Optional[float] = None,
    system_id: Optional[int] = None,
) -> Tuple[float, float, int]:
    """
    Resolve manufacturing/reaction indices for a facility.

    Uses the facility profile's solar system (Amamake → 30002537,
    Basgerin → 30002666) and pulls live ESI values unless both indexes are
    explicitly overridden.
    """
    resolved_system_id = (
        int(system_id)
        if system_id is not None
        else get_facility_system_id(facility)
    )
    if manufacturing_index is not None and reaction_index is not None:
        return (
            float(manufacturing_index),
            float(reaction_index),
            resolved_system_id,
        )

    live_mfg, live_rxn = fetch_system_cost_indices(resolved_system_id)
    return (
        (
            float(manufacturing_index)
            if manufacturing_index is not None
            else live_mfg
        ),
        float(reaction_index) if reaction_index is not None else live_rxn,
        resolved_system_id,
    )


def _adjusted_prices(type_ids: Iterable[int]) -> Dict[int, float]:
    ids = list(set(type_ids))
    if not ids:
        return {}
    return {
        type_id: float(price or 0.0)
        for type_id, price in EveMarketPrice.objects.filter(
            eve_type_id__in=ids
        ).values_list("eve_type_id", "adjusted_price")
    }


def _assign_buckets(
    jobs_meta: Dict[int, Tuple[Recipe, int, JobClass]],
    root_type_id: int,
) -> Dict[int, JobBucket]:
    """Classify each planned product into Ravworks-style buckets."""
    reaction_ids = {
        pid
        for pid, (recipe, _, _) in jobs_meta.items()
        if recipe.activity_id == ACTIVITY_REACTION
    }
    manufacturing_inputs: Set[int] = set()
    for recipe, _, _ in jobs_meta.values():
        if recipe.activity_id == ACTIVITY_MANUFACTURING:
            for mid, _, _ in recipe.materials:
                manufacturing_inputs.add(mid)

    second_stage = {pid for pid in reaction_ids if pid in manufacturing_inputs}
    first_stage = reaction_ids - second_stage

    buckets: Dict[int, JobBucket] = {}
    for pid in jobs_meta:
        if pid == root_type_id:
            buckets[pid] = JobBucket.END_PRODUCT
        elif pid in first_stage:
            buckets[pid] = JobBucket.FIRST_STAGE_REACTIONS
        elif pid in second_stage:
            buckets[pid] = JobBucket.SECOND_STAGE_REACTIONS
        elif _is_advanced_component(pid):
            buckets[pid] = JobBucket.ADVANCED_COMPONENTS
        else:
            buckets[pid] = JobBucket.OTHER
    return buckets


def _resolve_root_product(product: EveType | str | int) -> EveType:
    if isinstance(product, EveType):
        return product
    if isinstance(product, int):
        return resolve_product(str(product))
    return resolve_product(product)


def _stabilize_demand(
    *,
    root_id: int,
    quantity: int,
    blueprint_me: float,
    profile: Dict[JobClass, FacilityBonuses],
    is_buildable,
    recipe_for,
) -> Tuple[Dict[int, int], Dict[int, Tuple[Recipe, int, JobClass]]]:
    """Iterate until run counts stabilize (ME can change upstream demand)."""
    demand: Dict[int, int] = defaultdict(int)
    demand[root_id] = quantity
    jobs_meta: Dict[int, Tuple[Recipe, int, JobClass]] = {}

    for _ in range(40):
        new_demand: Dict[int, int] = defaultdict(int)
        new_demand[root_id] = quantity
        next_jobs: Dict[int, Tuple[Recipe, int, JobClass]] = {}

        for type_id, needed in list(demand.items()):
            if not is_buildable(type_id):
                continue
            recipe = recipe_for(type_id)
            if recipe is None:
                continue
            runs = ceil(needed / recipe.product_quantity)
            job_class = _classify_job_class(recipe, root_id)
            bonuses = profile[job_class]
            bp_me = (
                0.0
                if recipe.activity_id == ACTIVITY_REACTION
                else blueprint_me
            )
            me_total = material_efficiency_total(
                bp_me, bonuses.role_me, bonuses.rig_me
            )
            next_jobs[type_id] = (recipe, runs, job_class)
            for mid, _, base_qty in recipe.materials:
                new_demand[mid] += required_material_quantity(
                    runs, base_qty, me_total
                )

        if next_jobs == jobs_meta and new_demand == demand:
            break
        jobs_meta = next_jobs
        demand = new_demand
    else:
        logger.warning("Build plan demand did not fully stabilize")

    return demand, jobs_meta


def _build_job_plan(
    *,
    type_id: int,
    recipe: Recipe,
    runs: int,
    job_class: JobClass,
    bucket: JobBucket,
    profile: Dict[JobClass, FacilityBonuses],
    blueprint_me: float,
    blueprint_te: float,
    skills: SkillSettings,
    prices: Dict[int, float],
    manufacturing_index: float,
    reaction_index: float,
) -> JobPlan:
    bonuses = profile[job_class]
    is_reaction = recipe.activity_id == ACTIVITY_REACTION
    bp_me = 0.0 if is_reaction else blueprint_me
    bp_te = 0.0 if is_reaction else blueprint_te
    me_total = material_efficiency_total(
        bp_me, bonuses.role_me, bonuses.rig_me
    )
    te_mult = time_efficiency_multiplier(
        bp_te,
        bonuses.role_te,
        bonuses.rig_te,
        industry_level=skills.industry_level,
        advanced_industry_level=skills.advanced_industry_level,
        reaction_skill_level=skills.reaction_skill_level,
        implant_te=skills.implant_te,
        is_reaction=is_reaction,
    )
    materials = [
        MaterialLine(
            type_id=mid,
            name=name,
            quantity=required_material_quantity(runs, base_qty, me_total),
            base_quantity_per_run=base_qty,
        )
        for mid, name, base_qty in recipe.materials
    ]
    eiv = estimated_item_value(
        [
            (base_qty, prices.get(mid, 0.0))
            for mid, _, base_qty in recipe.materials
        ],
        runs,
    )
    index = reaction_index if is_reaction else manufacturing_index
    cost = job_installation_cost(
        eiv,
        index,
        structure_isk_bonus=bonuses.structure_isk_bonus,
        facility_tax=bonuses.facility_tax,
        scc_surcharge=bonuses.scc_surcharge,
        system_cost_bonus=bonuses.system_cost_bonus,
    )
    return JobPlan(
        product_type_id=type_id,
        product_name=recipe.product_name,
        activity_id=recipe.activity_id,
        job_class=job_class,
        bucket=bucket,
        runs=runs,
        facility_name=bonuses.structure_name,
        blueprint_me=bp_me,
        blueprint_te=bp_te,
        me_total=me_total,
        te_multiplier=te_mult,
        materials=materials,
        duration_seconds=job_duration_seconds(recipe.base_time, runs, te_mult),
        job_cost=cost,
        eiv=eiv,
    )


def _collect_leaf_materials(
    demand: Dict[int, int],
    is_buildable,
) -> Dict[int, Tuple[str, int]]:
    leaf_materials: Dict[int, Tuple[str, int]] = {}
    for type_id, qty in demand.items():
        if is_buildable(type_id) or qty <= 0:
            continue
        name = EveType.objects.filter(id=type_id).values_list(
            "name", flat=True
        ).first() or str(type_id)
        leaf_materials[type_id] = (name, qty)
    return leaf_materials


def plan_build(
    product: EveType | str | int,
    quantity: int = 1,
    blueprint_me: float = 0.10,
    blueprint_te: float = 0.20,
    facility: str = "amamake",
    skills: Optional[SkillSettings] = None,
    manufacturing_index: Optional[float] = None,
    reaction_index: Optional[float] = None,
    system_id: Optional[int] = None,
    build_fuel_blocks: bool = True,
    exclude_type_ids: Optional[Iterable[int]] = None,
) -> BuildPlan:
    """
    Expand `product` into a full job tree at the given facility profile.

    blueprint_me / blueprint_te are fractions (0.10 = ME 10, 0.20 = TE 20).
    Only applied to manufacturing jobs (reactions have no BP ME/TE).

    Cost indexes default to live ESI values for the facility's system
    (Amamake / Basgerin). Pass both manufacturing_index and reaction_index
    only for offline/tests.

    Types in ``exclude_type_ids`` are treated as imported leaves (subtree not
    expanded), matching ``build_fuel_blocks=False`` for fuel-block groups.
    The root product cannot be excluded.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    root = _resolve_root_product(product)
    skills = skills or SkillSettings()
    profile = get_facility_profile(facility)
    indices_overridden = (
        manufacturing_index is not None and reaction_index is not None
    )
    manufacturing_index, reaction_index, resolved_system_id = (
        resolve_cost_indices(
            facility,
            manufacturing_index=manufacturing_index,
            reaction_index=reaction_index,
            system_id=system_id,
        )
    )

    fuel_type_ids: Set[int] = set(
        EveType.objects.filter(eve_group_id=GROUP_FUEL_BLOCK).values_list(
            "id", flat=True
        )
    )
    excluded: Set[int] = {int(tid) for tid in (exclude_type_ids or [])}
    excluded.discard(int(root.id))

    recipe_cache: Dict[int, Optional[Recipe]] = {}

    def recipe_for(type_id: int) -> Optional[Recipe]:
        if type_id not in recipe_cache:
            recipe_cache[type_id] = _get_recipe(type_id)
        return recipe_cache[type_id]

    def is_buildable(type_id: int) -> bool:
        if type_id in excluded:
            return False
        if not build_fuel_blocks and type_id in fuel_type_ids:
            return False
        return recipe_for(type_id) is not None

    demand, jobs_meta = _stabilize_demand(
        root_id=root.id,
        quantity=quantity,
        blueprint_me=blueprint_me,
        profile=profile,
        is_buildable=is_buildable,
        recipe_for=recipe_for,
    )
    buckets = _assign_buckets(jobs_meta, root.id)

    all_mat_ids: List[int] = []
    for recipe, _, _ in jobs_meta.values():
        all_mat_ids.extend(mid for mid, _, _ in recipe.materials)
    prices = _adjusted_prices(all_mat_ids)

    job_plans: List[JobPlan] = [
        _build_job_plan(
            type_id=type_id,
            recipe=recipe,
            runs=runs,
            job_class=job_class,
            bucket=buckets[type_id],
            profile=profile,
            blueprint_me=blueprint_me,
            blueprint_te=blueprint_te,
            skills=skills,
            prices=prices,
            manufacturing_index=manufacturing_index,
            reaction_index=reaction_index,
        )
        for type_id, (recipe, runs, job_class) in sorted(
            jobs_meta.items(), key=lambda item: item[1][0].product_name
        )
    ]

    return BuildPlan(
        product_type_id=root.id,
        product_name=root.name,
        quantity=quantity,
        blueprint_me=blueprint_me,
        blueprint_te=blueprint_te,
        facility_key=facility,
        system_id=resolved_system_id,
        manufacturing_index=manufacturing_index,
        reaction_index=reaction_index,
        indices_from_esi=not indices_overridden,
        jobs=job_plans,
        leaf_materials=_collect_leaf_materials(demand, is_buildable),
    )


def plan_to_dict(plan: BuildPlan) -> Dict[str, Any]:
    """JSON-serializable representation of a build plan."""
    return {
        "product": {
            "type_id": plan.product_type_id,
            "name": plan.product_name,
            "quantity": plan.quantity,
        },
        "blueprint_me": plan.blueprint_me,
        "blueprint_te": plan.blueprint_te,
        "facility": plan.facility_key,
        "system_id": plan.system_id,
        "manufacturing_index": plan.manufacturing_index,
        "reaction_index": plan.reaction_index,
        "indices_from_esi": plan.indices_from_esi,
        "total_duration_seconds": plan.total_duration_seconds,
        "total_job_cost_isk": plan.total_job_cost_isk,
        "bucket_durations": {
            b.value: secs for b, secs in plan.bucket_duration_seconds().items()
        },
        "jobs": [
            {
                "product_type_id": j.product_type_id,
                "product_name": j.product_name,
                "activity_id": j.activity_id,
                "job_class": j.job_class.value,
                "bucket": j.bucket.value,
                "runs": j.runs,
                "facility": j.facility_name,
                "blueprint_me": j.blueprint_me,
                "blueprint_te": j.blueprint_te,
                "me_total": j.me_total,
                "te_multiplier": j.te_multiplier,
                "duration_seconds": j.duration_seconds,
                "eiv": j.eiv,
                "job_cost_isk": j.job_cost.total,
                "materials": [
                    {
                        "type_id": m.type_id,
                        "name": m.name,
                        "quantity": m.quantity,
                    }
                    for m in j.materials
                ],
            }
            for j in plan.jobs
        ],
        "leaf_materials": [
            {"type_id": tid, "name": name, "quantity": qty}
            for tid, (name, qty) in sorted(
                plan.leaf_materials.items(), key=lambda x: x[1][0]
            )
        ],
    }
