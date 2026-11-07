"""POST /plans - calculate a full manufacture/reaction job plan for a product."""

from dataclasses import asdict

from eveuniverse.models import EveType

from app.cache import cache_get, cache_set
from app.errors import ErrorResponse
from authentication import AuthOptional
from buyback.helpers.purchase_refine import build_purchase_refine
from eveonline.models import EveCharacter
from industry.endpoints.planner.auth_helpers import auth_required_for_character
from industry.endpoints.planner.schemas import (
    PlanLeafMaterialSchema,
    PlanRequestSchema,
    PlanResponseSchema,
    PlanStockAppliedSchema,
)
from industry.helpers.blueprint_efficiency import (
    default_blueprint_me_te_percent,
    is_faction_navy_hull,
)
from industry.helpers.build_planner import RootBlueprint, plan_build
from industry.helpers.cost_breakdown import jita_sell_unit_prices_by_type_id
from industry.helpers.compressed_ore import (
    build_compressed_ore_plan,
    compression_covered_materials,
)
from industry.helpers.facility_api import normalize_me_te
from industry.helpers.plan_costing import (
    FreightOptions,
    cost_build_plan,
)
from industry.helpers.facility_profiles import (
    FACILITY_PROFILES,
    get_facility_reprocessing_tax,
)
from industry.helpers.invention import (
    BASE_COPY_ME,
    BASE_COPY_TE,
    InventionSkills,
)
from industry.helpers.invention_planner import (
    InventionRequest,
    invention_to_dict,
    is_invented_product,
    plan_invented_build,
)
from industry.helpers.loyalty_store import (
    get_offer_for_blueprint_type,
    navy_bpc_cost_for_plan,
    resolve_isk_per_lp,
)
from industry.helpers import plan_step_savings
from industry.helpers.plan_stock import (
    apply_stock_to_compressed_ore_plan,
    apply_stock_to_leaf_materials,
    credit_reprocessed_ore_stock,
    parse_stock_paste,
)
from industry.helpers.reprocessing_skills import (
    compression_ore_refine_yields,
    ore_refine_yields_payload,
    resolve_refine_rate,
)
from industry.helpers.type_breakdown import get_blueprint_or_reaction_type_id

PATH = "plans"
METHOD = "post"
ROUTE_SPEC = {
    "summary": (
        "Plan manufacture + reaction jobs for a product at an alliance freeport "
        "(live ESI cost indices); optional compressed-ore/ice conversion. "
        "Anonymous callers get max-skill refine assumptions; character_id "
        "requires authentication. Optional stock_paste subtracts on-hand "
        "inventory from the shopping list."
    ),
    "auth": AuthOptional(),
    "response": {
        200: PlanResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        502: ErrorResponse,
    },
}


def _leaf_materials_multibuy(leaf_materials) -> str:
    """EVE Online Multibuy paste format: ``Name Quantity`` per line."""
    rows = [f"{row.name} {row.quantity}" for row in leaf_materials]
    return "\r\n".join(rows)


def _character_skills_payload(skills) -> dict:
    return {
        "character_id": skills.character_id,
        "character_name": skills.character_name,
        "reprocessing_level": skills.reprocessing_level,
        "reprocessing_efficiency_level": skills.reprocessing_efficiency_level,
        "simple_ore_processing_level": skills.simple_ore_processing_level,
        "coherent_ore_processing_level": skills.coherent_ore_processing_level,
        "ubiquitous_moon_ore_processing_level": (
            skills.ubiquitous_moon_ore_processing_level
        ),
        "ore_processing_level": skills.ore_processing_level,
        "implant_bonus": skills.implant_bonus,
        "implant_type_id": skills.implant_type_id,
        "implant_name": skills.implant_name,
        "use_reprocessing_implants": skills.use_reprocessing_implants,
    }


def _leaf_materials_with_prices(plan):
    """Leaf materials at the planner's own unit price (industry Jita sell)."""
    type_ids = list(plan.leaf_materials.keys())
    prices = {
        tid: float(price or 0.0)
        for tid, price in jita_sell_unit_prices_by_type_id(type_ids).items()
    }
    leaf_materials = []
    total_buy = 0.0
    for tid, (name, qty) in sorted(
        plan.leaf_materials.items(), key=lambda item: item[1][0]
    ):
        avg = prices.get(tid, 0.0)
        buy = qty * avg
        total_buy += buy
        leaf_materials.append(
            PlanLeafMaterialSchema(
                type_id=tid,
                name=name,
                quantity=qty,
                average_price=avg,
                estimated_buy_isk=buy,
            )
        )
    return leaf_materials, total_buy


def _compressed_payload_from_ore_plan(
    ore_plan, rate_source, skills, ore_yields
) -> dict:
    return {
        "refine_rate": ore_plan.refine_rate,
        "refine_rate_source": rate_source,
        "reprocessing_tax": ore_plan.reprocessing_tax,
        "materials_tsv": ore_plan.multibuy(),
        "import_lines": [
            {"name": name, "quantity": qty}
            for name, qty in ore_plan.import_lines()
        ],
        "compression_covered": compression_covered_materials(),
        "belt_ore_compressed": dict(ore_plan.belt_ore_compressed),
        "moon_ore_compressed": dict(ore_plan.moon_ore_compressed),
        "ice_compressed": dict(ore_plan.ice_compressed),
        "mineral_imports": dict(ore_plan.mineral_imports),
        "pi_other_imports": dict(ore_plan.pi_other_imports),
        "ice_imports": dict(ore_plan.ice_imports),
        "other_imports": dict(ore_plan.other_imports),
        "expected_minerals": dict(ore_plan.expected_minerals),
        "expected_ice_products": dict(ore_plan.expected_ice_products),
        "mineral_delta": dict(ore_plan.mineral_delta),
        "character_skills": (
            _character_skills_payload(skills) if skills else None
        ),
        "ore_yields": ore_refine_yields_payload(ore_yields),
    }


def _build_compressed_ore_section(plan, facility_key, character, payload):
    """Return (compressed_payload, ore_plan) or (error_status, ErrorResponse)."""
    try:
        refine, rate_source, skills = resolve_refine_rate(
            facility_key,
            character=character,
            use_reprocessing_implants=payload.use_reprocessing_implants,
            refine_rate_override=payload.refine_rate,
        )
        ore_yields = compression_ore_refine_yields(
            facility_key,
            skills=skills,
            use_reprocessing_implants=payload.use_reprocessing_implants,
            refine_rate_override=payload.refine_rate,
        )
    except ValueError as exc:
        return 400, ErrorResponse(detail=str(exc))

    materials = {name: qty for _, (name, qty) in plan.leaf_materials.items()}
    ore_plan = build_compressed_ore_plan(
        materials,
        refine_rate=refine,
        reprocessing_tax=get_facility_reprocessing_tax(facility_key),
    )
    compressed_payload = _compressed_payload_from_ore_plan(
        ore_plan, rate_source, skills, ore_yields
    )
    return compressed_payload, ore_plan


def _stock_applied_payload(rows) -> list:
    return [
        PlanStockAppliedSchema(
            type_id=row.type_id,
            name=row.name,
            needed=row.needed,
            owned=row.owned,
            used=row.used,
            remaining=row.remaining,
        )
        for row in rows
    ]


def _apply_stock_paste(plan, payload):
    """Subtract pasted inventory from leaf materials; return applied + stock."""
    stock = parse_stock_paste(payload.stock_paste)
    if not stock.by_type_id and not stock.unresolved_names:
        return [], stock
    remaining, applied = apply_stock_to_leaf_materials(
        plan.leaf_materials,
        stock.by_type_id,
        stock_by_name=stock.by_name,
    )
    plan.leaf_materials = remaining
    return applied, stock


def _credit_variant_ore_stock(plan, stock, key, character, payload):
    """Credit II/III/IV and moon-variant ore as reprocessed minerals."""
    if stock is None or not stock.by_name:
        return []
    refine_holder: list = []

    def refine_rate_for(name: str) -> float:
        if payload.refine_rate is not None:
            return float(payload.refine_rate)
        if not refine_holder:
            refine_holder.append(
                build_purchase_refine(
                    character=character,
                    facility_key=key,
                    use_reprocessing_implants=payload.use_reprocessing_implants,
                )
            )
        return refine_holder[0].rate_for_ore(name)

    return credit_reprocessed_ore_stock(
        plan.leaf_materials,
        stock.by_type_id,
        stock.by_name,
        name_to_type_id=stock.name_to_type_id,
        refine_rate_for=refine_rate_for,
    )


def _refresh_compressed_payload_after_stock(compressed_payload, ore_plan):
    compressed_payload["materials_tsv"] = ore_plan.multibuy()
    compressed_payload["import_lines"] = [
        {"name": name, "quantity": qty}
        for name, qty in ore_plan.import_lines()
    ]
    compressed_payload["belt_ore_compressed"] = dict(
        ore_plan.belt_ore_compressed
    )
    compressed_payload["moon_ore_compressed"] = dict(
        ore_plan.moon_ore_compressed
    )
    compressed_payload["ice_compressed"] = dict(ore_plan.ice_compressed)
    compressed_payload["mineral_imports"] = dict(ore_plan.mineral_imports)
    compressed_payload["pi_other_imports"] = dict(ore_plan.pi_other_imports)
    compressed_payload["ice_imports"] = dict(ore_plan.ice_imports)
    compressed_payload["other_imports"] = dict(ore_plan.other_imports)
    compressed_payload["expected_minerals"] = dict(ore_plan.expected_minerals)
    compressed_payload["expected_ice_products"] = dict(
        ore_plan.expected_ice_products
    )
    compressed_payload["mineral_delta"] = dict(ore_plan.mineral_delta)
    compressed_payload["reprocessing_tax"] = ore_plan.reprocessing_tax


def _apply_stock_then_compress(plan, key, character, payload, stock):
    """
    Build compressed Multibuy from post-stock leaf demand.

    Mineral / PI stock is subtracted from ``plan.leaf_materials`` first, so
    ``build_compressed_ore_plan`` sizes less ore/ice when on-hand minerals
    already cover part of the BOM. Remaining stock (e.g. Compressed Veldspar)
    is then applied to the ore shopping list.

    Returns ``(error, compressed_payload, ore_plan, ore_applied)`` where
    ``error`` is an ``(status, ErrorResponse)`` tuple on failure.
    """
    result = _build_compressed_ore_section(plan, key, character, payload)
    if isinstance(result[1], ErrorResponse):
        return result, None, None, None
    compressed_payload, ore_plan = result
    ore_applied = []
    if stock is not None and stock.by_name:
        ore_applied = apply_stock_to_compressed_ore_plan(
            ore_plan,
            stock.by_name,
            name_to_type_id=stock.name_to_type_id,
        )
        if ore_applied:
            _refresh_compressed_payload_after_stock(
                compressed_payload, ore_plan
            )
    return None, compressed_payload, ore_plan, ore_applied


def _plan_response_body(
    plan,
    leaf_materials,
    total_buy,
    materials_tsv,
    compressed_payload,
    ore_plan,
    navy_bpc=None,
    stock_applied=None,
    stock_unresolved=None,
    step_savings=None,
    blueprint=None,
):
    navy_bpc_isk = navy_bpc.total_isk if navy_bpc is not None else 0
    cost_breakdown = cost_build_plan(
        plan,
        compressed_ore=ore_plan,
        navy_bpc_isk=navy_bpc_isk,
        input_freight=FreightOptions.alliance_default(),
        include_line_items=True,
    )
    return {
        "product": {
            "type_id": plan.product_type_id,
            "name": plan.product_name,
            "quantity": plan.quantity,
        },
        "blueprint_me": plan.blueprint_me,
        "blueprint_te": plan.blueprint_te,
        **_blueprint_payload(plan, blueprint),
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
                "job_count": j.job_count,
                "runs_per_job": j.runs_per_job,
                "remainder_runs": j.remainder_runs,
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
        "leaf_materials": leaf_materials,
        "estimated_materials_buy_isk": total_buy,
        "materials_tsv": materials_tsv,
        "compressed_ore": compressed_payload,
        "cost_breakdown": cost_breakdown.to_legacy_breakdown_dict(),
        "navy_bpc": navy_bpc.to_dict() if navy_bpc is not None else None,
        "invention": (
            invention_to_dict(plan.invention)
            if plan.invention is not None
            else None
        ),
        "stock_applied": _stock_applied_payload(stock_applied or []),
        "stock_unresolved": list(stock_unresolved or []),
        "step_savings": [
            {
                "type_id": row.type_id,
                "name": row.name,
                "quantity": row.quantity,
                "build_isk": row.build_isk,
                "buy_isk": row.buy_isk,
                "saving_isk": row.saving_isk,
            }
            for row in (step_savings or [])
        ],
    }


def _blueprint_payload(plan, blueprint) -> dict:
    """Which blueprint the root is built from, plus the tree's BPO defaults."""
    source, default_me, default_te = blueprint or ("bpo", 10.0, 20.0)
    root = plan.root_blueprint
    return {
        "blueprint_source": source,
        "default_blueprint_me": default_me,
        "default_blueprint_te": default_te,
        "root_blueprint_me": root.me * 100.0 if root else None,
        "root_blueprint_te": root.te * 100.0 if root else None,
        "root_runs_per_copy": root.runs_per_copy if root else None,
    }


def _invention_skills(payload) -> InventionSkills:
    skills = payload.invention_skills
    if skills is None:
        return InventionSkills()
    levels = (skills.science_1, skills.science_2, skills.encryption)
    if any(level < 0 or level > 5 for level in levels):
        raise ValueError("invention skill levels must be 0-5")
    return InventionSkills(
        science_1=skills.science_1,
        science_2=skills.science_2,
        encryption=skills.encryption,
    )


def _resolve_root_blueprint(eve_type, payload):
    """(source, InventionRequest | None, RootBlueprint | None) for the root.

    Raises ValueError for a bad blueprint_source, ME/TE or skill level.
    """
    if is_faction_navy_hull(eve_type):
        return "navy_bpc", None, None
    if not is_invented_product(eve_type.id):
        return "bpo", None, None
    source = (payload.blueprint_source or "invent").strip().lower()
    if source == "supplied_bpc":
        me = normalize_me_te(
            BASE_COPY_ME if payload.bpc_me is None else payload.bpc_me
        )
        te = normalize_me_te(
            BASE_COPY_TE if payload.bpc_te is None else payload.bpc_te
        )
        return source, None, RootBlueprint(me=me, te=te)
    if source != "invent":
        raise ValueError("blueprint_source must be 'invent' or 'supplied_bpc'")
    request = InventionRequest(
        decryptor=(payload.decryptor or "auto").strip().lower(),
        source_type_id=payload.invention_source_type_id,
        skills=_invention_skills(payload),
    )
    return source, request, None


def _resolve_navy_bpc(eve_type, payload):
    """Optional navy BPC LP cost from persisted offers + isk_per_lp."""
    if not is_faction_navy_hull(eve_type):
        return None
    blueprint_type_id = get_blueprint_or_reaction_type_id(eve_type)
    if blueprint_type_id is None:
        return None
    offer = get_offer_for_blueprint_type(blueprint_type_id)
    corporation_id = offer.corporation_id if offer is not None else None
    rate = resolve_isk_per_lp(
        requested=payload.isk_per_lp,
        corporation_id=corporation_id,
    )
    if rate is None:
        return None
    return navy_bpc_cost_for_plan(
        blueprint_type_id,
        payload.quantity,
        float(rate),
    )


def _resolve_plan_request(request, payload: PlanRequestSchema):
    """Validate payload and resolve entities.

    Returns ((key, eve_type, character, me, te, exclude_type_ids, root), None)
    or (None, (status, ErrorResponse)). ``root`` is
    ``(blueprint_source, InventionRequest | None, RootBlueprint | None)``.
    """
    if payload.quantity < 1:
        return None, (400, ErrorResponse(detail="quantity must be >= 1"))

    key = payload.facility_key.lower().strip()
    if key not in FACILITY_PROFILES:
        return None, (
            400,
            ErrorResponse(detail=f"Unknown facility {payload.facility_key!r}"),
        )

    eve_type = EveType.objects.filter(id=payload.product_type_id).first()
    if eve_type is None:
        return None, (
            400,
            ErrorResponse(
                detail=f"Unknown product_type_id {payload.product_type_id}"
            ),
        )

    auth_error = auth_required_for_character(request, payload.character_id)
    if auth_error is not None:
        return None, auth_error

    character = None
    if payload.character_id is not None:
        character = EveCharacter.objects.filter(
            character_id=payload.character_id
        ).first()
        if character is None:
            return None, (
                400,
                ErrorResponse(
                    detail=f"Unknown character_id {payload.character_id}"
                ),
            )

    default_me, default_te = default_blueprint_me_te_percent(eve_type)
    try:
        me = normalize_me_te(
            default_me
            if payload.blueprint_me is None
            else payload.blueprint_me
        )
        te = normalize_me_te(
            default_te
            if payload.blueprint_te is None
            else payload.blueprint_te
        )
    except ValueError as exc:
        return None, (400, ErrorResponse(detail=str(exc)))

    if payload.max_runs_per_job is not None and payload.max_runs_per_job < 1:
        return None, (
            400,
            ErrorResponse(detail="max_runs_per_job must be at least 1"),
        )

    exclude_type_ids = list(payload.exclude_type_ids or [])
    if payload.product_type_id in exclude_type_ids:
        return None, (
            400,
            ErrorResponse(
                detail=(
                    "exclude_type_ids cannot include the root product_type_id"
                )
            ),
        )

    try:
        root = _resolve_root_blueprint(eve_type, payload)
    except ValueError as exc:
        return None, (400, ErrorResponse(detail=str(exc)))

    return (key, eve_type, character, me, te, exclude_type_ids, root), None


def _execute_plan_build(
    eve_type, payload, key, me, te, exclude_type_ids, root
):
    _, invention_request, root_blueprint = root
    kwargs = {
        "quantity": payload.quantity,
        "blueprint_me": me,
        "blueprint_te": te,
        "facility": key,
        "build_fuel_blocks": payload.build_fuel_blocks,
        "exclude_type_ids": exclude_type_ids,
        "max_runs_per_job": payload.max_runs_per_job,
    }
    try:
        if invention_request is not None:
            return plan_invented_build(
                eve_type, request=invention_request, **kwargs
            )
        return plan_build(eve_type, root_blueprint=root_blueprint, **kwargs)
    except ValueError as exc:
        msg = str(exc)
        if "cost index" in msg.lower() or "esi" in msg.lower():
            return 502, ErrorResponse(detail=msg)
        return 400, ErrorResponse(detail=msg)


# Ticking a step replans with the same full tree, so the savings are cached
# briefly rather than expanding the whole tree again on every toggle.
STEP_SAVINGS_TTL_SECONDS = 600


def _step_savings_cache_key(payload, key, me, te) -> str:
    parts = [
        payload.product_type_id,
        payload.quantity,
        me,
        te,
        key,
        int(bool(payload.build_fuel_blocks)),
        payload.max_runs_per_job or 0,
        # T2/T3: the root copy changes the root's demand for every step.
        payload.blueprint_source or "",
        payload.decryptor or "",
        payload.invention_source_type_id or 0,
        payload.bpc_me if payload.bpc_me is not None else "",
        payload.bpc_te if payload.bpc_te is not None else "",
        (
            payload.invention_skills.model_dump_json()
            if payload.invention_skills is not None
            else ""
        ),
    ]
    return "industry_plan_step_savings:v2:" + ":".join(str(p) for p in parts)


def _step_savings(
    plan, eve_type, payload, key, me, te, exclude_type_ids, root
):
    """
    Build-vs-buy saving for every intermediate, ticked or not.

    Bought steps have no job in ``plan``, so this values the steps from the
    fully expanded plan (same settings, nothing excluded). A step's own job
    and the units its parents consume are the same in any plan that builds
    it.
    """
    cache_key = _step_savings_cache_key(payload, key, me, te)
    if exclude_type_ids:
        cached = cache_get(cache_key)
        if cached is not None:
            return [plan_step_savings.StepSaving(**row) for row in cached]
        full_plan = _execute_plan_build(
            eve_type, payload, key, me, te, [], root
        )
        if isinstance(full_plan, tuple):
            return []
    else:
        full_plan = plan
    savings = plan_step_savings.plan_step_savings(full_plan)
    cache_set(
        cache_key,
        [asdict(row) for row in savings],
        STEP_SAVINGS_TTL_SECONDS,
    )
    return savings


def post_plan(request, payload: PlanRequestSchema):
    resolved, error = _resolve_plan_request(request, payload)
    if error is not None:
        return error
    key, eve_type, character, me, te, exclude_type_ids, root = resolved

    plan = _execute_plan_build(
        eve_type, payload, key, me, te, exclude_type_ids, root
    )
    if isinstance(plan, tuple):
        return plan
    step_savings = _step_savings(
        plan, eve_type, payload, key, me, te, exclude_type_ids, root
    )

    stock_applied_rows = []
    stock_unresolved = []
    stock = None
    if payload.stock_paste:
        leaf_applied, stock = _apply_stock_paste(plan, payload)
        stock_applied_rows.extend(leaf_applied)
        stock_applied_rows.extend(
            _credit_variant_ore_stock(plan, stock, key, character, payload)
        )
        stock_unresolved = list(stock.unresolved_names)

    leaf_materials, total_buy = _leaf_materials_with_prices(plan)
    materials_tsv = _leaf_materials_multibuy(leaf_materials)
    compressed_payload = None
    ore_plan = None

    if payload.compressed:
        error, compressed_payload, ore_plan, ore_applied = (
            _apply_stock_then_compress(plan, key, character, payload, stock)
        )
        if error is not None:
            return error
        if ore_applied:
            stock_applied_rows.extend(ore_applied)
        materials_tsv = ore_plan.multibuy()

    navy_bpc = _resolve_navy_bpc(eve_type, payload)

    return _plan_response_body(
        plan,
        leaf_materials,
        total_buy,
        materials_tsv,
        compressed_payload,
        ore_plan,
        navy_bpc=navy_bpc,
        stock_applied=stock_applied_rows,
        stock_unresolved=stock_unresolved,
        step_savings=step_savings,
        blueprint=(root[0], *default_blueprint_me_te_percent(eve_type)),
    )
