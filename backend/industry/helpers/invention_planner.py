"""Invention in the build planner: quote the copy, then plan the build from it.

``quote_invention`` prices every way to invent a product's blueprint copy at a
facility (each source × each decryptor) and picks the cheapest per unit.
``plan_invented_build`` runs the normal planner with the chosen copy's ME/TE
and runs on the root job and attaches the quote as ``plan.invention``.

Prices: datacores, decryptors, relics and root materials use the planner's
Jita sell (``jita_sell_unit_prices_by_type_id``). Install fees use ESI
adjusted prices for EIV (``build_planner.adjusted_prices``), like every
other planner job.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Union

from eveuniverse.models import EveType

from industry.helpers.build_planner import (
    BuildPlan,
    Recipe,
    RootBlueprint,
    adjusted_prices,
    classify_job_class,
    get_recipe,
    plan_build,
    resolve_cost_indices,
    resolve_product,
)
from industry.helpers.cost_breakdown import jita_sell_unit_prices_by_type_id
from industry.helpers.cost_indices import fetch_system_science_indices
from industry.helpers.facility_profiles import (
    FacilityBonuses,
    JobClass,
    get_facility_profile,
)
from industry.helpers.industry_formulas import (
    batched_job_installation_cost,
    batched_material_quantity,
    job_installation_cost,
    material_efficiency_total,
)
from industry.helpers.invention import (
    AUTO,
    NO_DECRYPTOR,
    NONE,
    AttemptInput,
    DecryptorOption,
    FeeParts,
    InventionChoice,
    InventionQuote,
    InventionSkills,
    SourceOption,
    choose,
)
from industry.models import InventionDecryptor, InventionOutcome

# Invention and copy jobs are charged on 2% of the EIV of what they make.
SCIENCE_EIV_SHARE = 0.02


@dataclass(frozen=True)
class InventionRequest:
    """How to invent: decryptor ("auto", "none" or a type id) and source."""

    decryptor: Union[str, int] = AUTO
    source_type_id: Optional[int] = None
    skills: InventionSkills = field(default_factory=InventionSkills)


def invention_outcomes(product_type_id: int) -> List[InventionOutcome]:
    return list(
        InventionOutcome.objects.filter(
            product_type_id=int(product_type_id)
        ).order_by("-probability", "source_type_id")
    )


def is_invented_product(product_type_id: int) -> bool:
    """True when the product's blueprint comes from invention (T2 / T3)."""
    return InventionOutcome.objects.filter(
        product_type_id=int(product_type_id)
    ).exists()


def tech_kind(outcomes: Iterable[InventionOutcome]) -> str:
    """ "T3" when any source is a relic, else "T2"."""
    for outcome in outcomes:
        if outcome.source_kind == InventionOutcome.SOURCE_RELIC:
            return "T3"
    return "T2"


def _decryptor_options(
    request: InventionRequest, prices: Dict[int, float]
) -> List[DecryptorOption]:
    rows = list(InventionDecryptor.objects.all())
    options: List[DecryptorOption] = []
    for row in rows:
        price = prices.get(row.type_id)
        explicit = str(request.decryptor) == str(row.type_id)
        if price is None and not explicit:
            # No market price: never pick it by accident at 0 ISK.
            continue
        options.append(
            DecryptorOption(
                type_id=row.type_id,
                name=row.name,
                probability_multiplier=row.probability_multiplier,
                runs_modifier=row.runs_modifier,
                me_modifier=row.me_modifier,
                te_modifier=row.te_modifier,
                unit_price=float(price or 0.0),
            )
        )
    choice = str(request.decryptor).lower()
    if choice == AUTO:
        return [NO_DECRYPTOR, *options]
    if choice == NONE:
        return [NO_DECRYPTOR]
    chosen = [o for o in options if str(o.type_id) == choice]
    if not chosen:
        raise ValueError(f"Unknown decryptor {request.decryptor!r}")
    return chosen


def _fee(eiv: float, index: float, bonuses: FacilityBonuses) -> FeeParts:
    cost = job_installation_cost(
        eiv,
        index,
        structure_isk_bonus=bonuses.structure_isk_bonus,
        facility_tax=bonuses.facility_tax,
        scc_surcharge=bonuses.scc_surcharge,
        system_cost_bonus=bonuses.system_cost_bonus,
    )
    return FeeParts(
        gross=cost.gross_cost,
        facility_tax=cost.facility_tax_isk,
        scc=cost.scc_tax_isk,
    )


def _science_time_multiplier(bonuses: FacilityBonuses) -> float:
    return (1.0 - bonuses.role_te) * (1.0 - bonuses.rig_te)


def _eiv_per_run(recipe: Optional[Recipe], prices: Dict[int, float]) -> float:
    if recipe is None:
        return 0.0
    return sum(qty * prices.get(mid, 0.0) for mid, _, qty in recipe.materials)


@dataclass(frozen=True)
class _QuoteContext:
    """Prices, fees and bonuses shared by every source of one product."""

    science: FacilityBonuses
    invention_index: float
    copying_index: float
    eiv_prices: Dict[int, float]
    jita: Dict[int, float]
    names: Dict[int, str]
    t1_recipes: Dict[int, Optional[Recipe]]
    invention_fee: FeeParts
    skills: InventionSkills


def _resolve_indices(
    facility: str,
    manufacturing_index: Optional[float],
    invention_index: Optional[float],
    copying_index: Optional[float],
):
    """(manufacturing, invention, copying) indices; overrides win."""
    mfg_index, _, system_id = resolve_cost_indices(
        facility,
        manufacturing_index=manufacturing_index,
        reaction_index=0.0 if manufacturing_index is not None else None,
    )
    if invention_index is None or copying_index is None:
        live_inv, live_copy = fetch_system_science_indices(system_id)
        if invention_index is None:
            invention_index = live_inv
        if copying_index is None:
            copying_index = live_copy
    return mfg_index, invention_index, copying_index


def _market_type_ids(
    recipe: Recipe, outcomes: List[InventionOutcome]
) -> List[int]:
    ids = {mid for mid, _, _ in recipe.materials}
    for outcome in outcomes:
        ids.update(int(tid) for tid, _ in outcome.materials)
        if outcome.source_kind == InventionOutcome.SOURCE_RELIC:
            ids.add(outcome.source_type_id)
    ids.update(InventionDecryptor.objects.values_list("type_id", flat=True))
    return list(ids)


def _quote_context(
    recipe: Recipe,
    outcomes: List[InventionOutcome],
    science: FacilityBonuses,
    invention_index: float,
    copying_index: float,
    skills: InventionSkills,
) -> _QuoteContext:
    t1_recipes: Dict[int, Optional[Recipe]] = {
        o.source_type_id: get_recipe(o.source_product_type_id)
        for o in outcomes
        if o.source_product_type_id
    }
    eiv_type_ids = [mid for mid, _, _ in recipe.materials]
    for t1 in t1_recipes.values():
        if t1 is not None:
            eiv_type_ids.extend(mid for mid, _, _ in t1.materials)
    eiv_prices = adjusted_prices(eiv_type_ids)
    jita = {
        int(tid): float(price)
        for tid, price in jita_sell_unit_prices_by_type_id(
            _market_type_ids(recipe, outcomes)
        ).items()
        if price
    }
    names = dict(
        EveType.objects.filter(
            id__in={int(t) for o in outcomes for t, _ in o.materials}
        ).values_list("id", "name")
    )
    return _QuoteContext(
        science=science,
        invention_index=invention_index,
        copying_index=copying_index,
        eiv_prices=eiv_prices,
        jita=jita,
        names=names,
        t1_recipes=t1_recipes,
        invention_fee=_fee(
            SCIENCE_EIV_SHARE * _eiv_per_run(recipe, eiv_prices),
            invention_index,
            science,
        ),
        skills=skills,
    )


def _source_option(outcome: InventionOutcome, ctx: _QuoteContext):
    """One outcome priced: datacores (+ relic), fees and science times."""
    inputs = [
        AttemptInput(
            type_id=int(tid),
            name=ctx.names.get(int(tid), str(tid)),
            quantity=int(qty),
            unit_price=ctx.jita.get(int(tid), 0.0),
        )
        for tid, qty in outcome.materials
    ]
    time_mult = _science_time_multiplier(ctx.science)
    copy_fee = FeeParts()
    copy_seconds = 0.0
    if outcome.source_kind == InventionOutcome.SOURCE_RELIC:
        inputs.append(
            AttemptInput(
                type_id=outcome.source_type_id,
                name=outcome.source_name,
                quantity=1,
                unit_price=ctx.jita.get(outcome.source_type_id, 0.0),
            )
        )
    else:
        t1_eiv = _eiv_per_run(
            ctx.t1_recipes.get(outcome.source_type_id), ctx.eiv_prices
        )
        copy_fee = _fee(
            SCIENCE_EIV_SHARE * t1_eiv, ctx.copying_index, ctx.science
        )
        copy_seconds = (
            outcome.copy_time_seconds
            * time_mult
            * (1.0 - 0.05 * ctx.skills.science)
        )
    return SourceOption(
        source_type_id=outcome.source_type_id,
        source_name=outcome.source_name,
        source_kind=outcome.source_kind,
        base_probability=outcome.probability,
        base_runs=outcome.runs,
        inputs=tuple(inputs),
        invention_fee=ctx.invention_fee,
        copy_fee=copy_fee,
        invention_seconds=outcome.time_seconds
        * time_mult
        * (1.0 - 0.03 * ctx.skills.advanced_industry),
        copy_seconds=copy_seconds,
    )


def _root_build_cost(
    recipe: Recipe,
    bonuses: FacilityBonuses,
    quantity: int,
    jita: Dict[int, float],
    eiv_prices: Dict[int, float],
    manufacturing_index: float,
):
    """``build_cost(me, runs_per_copy)`` for the root job only.

    Materials at Jita sell plus the root's install fee. Children are
    priced at Jita here; the full plan is built once for the winner.
    """
    runs_needed = int(
        math.ceil(max(int(quantity), 1) / recipe.product_quantity)
    )
    product_eiv = _eiv_per_run(recipe, eiv_prices)

    def build_cost(me: float, runs_per_copy: int) -> float:
        me_total = material_efficiency_total(
            me, bonuses.role_me, bonuses.rig_me
        )
        materials = sum(
            batched_material_quantity(
                runs_needed, qty, me_total, runs_per_copy
            )
            * jita.get(mid, 0.0)
            for mid, _, qty in recipe.materials
        )
        fee = batched_job_installation_cost(
            product_eiv * runs_needed,
            runs_needed,
            runs_per_copy,
            system_cost_index=manufacturing_index,
            structure_isk_bonus=bonuses.structure_isk_bonus,
            facility_tax=bonuses.facility_tax,
            scc_surcharge=bonuses.scc_surcharge,
            system_cost_bonus=bonuses.system_cost_bonus,
        )
        return materials + fee.total

    return build_cost


def quote_invention(
    product: Union[EveType, int, str],
    quantity: int = 1,
    facility: str = "amamake",
    request: Optional[InventionRequest] = None,
    *,
    manufacturing_index: Optional[float] = None,
    invention_index: Optional[float] = None,
    copying_index: Optional[float] = None,
) -> InventionChoice:
    """Cheapest way to invent copies for ``quantity`` units at ``facility``."""
    request = request or InventionRequest()
    eve_type = (
        product
        if isinstance(product, EveType)
        else resolve_product(str(product))
    )
    outcomes = invention_outcomes(eve_type.id)
    if request.source_type_id is not None:
        outcomes = [
            o
            for o in outcomes
            if o.source_type_id == int(request.source_type_id)
        ]
    if not outcomes:
        raise ValueError(f"{eve_type.name} is not made by invention")
    recipe = get_recipe(eve_type.id)
    if recipe is None:
        raise ValueError(f"No manufacturing recipe for {eve_type.name}")

    profile = get_facility_profile(facility)
    mfg_index, invention_index, copying_index = _resolve_indices(
        facility, manufacturing_index, invention_index, copying_index
    )
    ctx = _quote_context(
        recipe,
        outcomes,
        profile[JobClass.SCIENCE],
        invention_index,
        copying_index,
        request.skills,
    )
    return choose(
        sources=[_source_option(outcome, ctx) for outcome in outcomes],
        decryptors=_decryptor_options(request, ctx.jita),
        skills=request.skills,
        units=max(int(quantity), 1),
        products_per_run=recipe.product_quantity,
        build_cost=_root_build_cost(
            recipe,
            profile[classify_job_class(recipe, eve_type.id)],
            quantity,
            ctx.jita,
            ctx.eiv_prices,
            mfg_index,
        ),
    )


def plan_invented_build(
    product: Union[EveType, int, str],
    quantity: int = 1,
    *,
    facility: str = "amamake",
    request: Optional[InventionRequest] = None,
    blueprint_me: float = 0.10,
    blueprint_te: float = 0.20,
    invention_index: Optional[float] = None,
    copying_index: Optional[float] = None,
    **plan_kwargs: Any,
) -> BuildPlan:
    """Plan an invented product: quote invention, then build from that copy.

    ``blueprint_me/te`` are the tree's BPOs (components, T1 hulls); the root
    uses the invented copy. Extra keyword arguments go to ``plan_build``.
    """
    eve_type = (
        product
        if isinstance(product, EveType)
        else resolve_product(str(product))
    )
    choice = quote_invention(
        eve_type,
        quantity,
        facility,
        request,
        manufacturing_index=plan_kwargs.get("manufacturing_index"),
        invention_index=invention_index,
        copying_index=copying_index,
    )
    best = choice.best
    plan = plan_build(
        eve_type,
        quantity=quantity,
        blueprint_me=blueprint_me,
        blueprint_te=blueprint_te,
        facility=facility,
        root_blueprint=RootBlueprint(
            me=best.copy_me / 100.0,
            te=best.copy_te / 100.0,
            runs_per_copy=best.runs_per_copy,
        ),
        **plan_kwargs,
    )
    plan.invention = choice
    return plan


def _quote_summary(q: InventionQuote) -> Dict[str, Any]:
    return {
        "source_type_id": q.source.source_type_id,
        "source_name": q.source.source_name,
        "source_kind": q.source.source_kind,
        "decryptor_type_id": q.decryptor.type_id,
        "decryptor_name": q.decryptor.name,
        "chance": q.chance,
        "runs_per_copy": q.runs_per_copy,
        "copy_me": q.copy_me,
        "copy_te": q.copy_te,
        "invention_per_unit_isk": q.invention_per_unit_isk,
        "per_unit_isk": q.per_unit_isk,
    }


def invention_to_dict(
    choice: InventionChoice, *, alternatives: int = 8
) -> Dict[str, Any]:
    """API shape for the chosen quote, its buy list and the runners-up."""
    best = choice.best
    inputs = [
        {
            "type_id": item.type_id,
            "name": item.name,
            "quantity_per_attempt": item.quantity,
            "unit_price": item.unit_price,
            "expected_quantity": item.quantity * best.expected_attempts,
            "buy_quantity": item.quantity * best.buy_attempts,
        }
        for item in best.source.inputs
    ]
    if best.decryptor.type_id is not None:
        inputs.append(
            {
                "type_id": best.decryptor.type_id,
                "name": best.decryptor.name,
                "quantity_per_attempt": 1,
                "unit_price": best.decryptor.unit_price,
                "expected_quantity": best.expected_attempts,
                "buy_quantity": best.buy_attempts,
            }
        )
    seen = {(best.source.source_type_id, best.decryptor.type_id)}
    others: List[Dict[str, Any]] = []
    for q in choice.alternatives:
        key = (q.source.source_type_id, q.decryptor.type_id)
        if key in seen:
            continue
        seen.add(key)
        others.append(_quote_summary(q))
        if len(others) >= alternatives:
            break
    return {
        **_quote_summary(best),
        "kind": (
            "T3"
            if best.source.source_kind == InventionOutcome.SOURCE_RELIC
            else "T2"
        ),
        "units": best.units,
        "runs_needed": best.runs_needed,
        "copies_needed": best.copies_needed,
        "expected_attempts": best.expected_attempts,
        "buy_attempts": best.buy_attempts,
        "attempts_p90": best.attempts_p90,
        "attempt_isk": best.attempt_isk,
        "invention_materials_isk": best.invention_materials_isk,
        "invention_job_costs_isk": best.invention_job_costs_isk,
        "invention_isk": best.invention_isk,
        "science_seconds": best.science_seconds,
        "inputs": inputs,
        "alternatives": others,
    }
