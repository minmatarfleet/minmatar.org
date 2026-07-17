"""POST /plans - calculate a full manufacture/reaction job plan for a product."""

from eveuniverse.models import EveMarketPrice, EveType

from app.errors import ErrorResponse
from authentication import AuthOptional
from eveonline.models import EveCharacter
from industry.endpoints.planner.auth_helpers import auth_required_for_character
from industry.endpoints.planner.schemas import (
    PlanLeafMaterialSchema,
    PlanRequestSchema,
    PlanResponseSchema,
)
from industry.helpers.blueprint_efficiency import (
    default_blueprint_me_te_percent,
    is_faction_navy_hull,
)
from industry.helpers.build_planner import plan_build
from industry.helpers.compressed_ore import (
    build_compressed_ore_plan,
    compression_covered_materials,
)
from industry.helpers.cost_breakdown import build_plan_cost_breakdown
from industry.helpers.facility_api import normalize_me_te
from industry.helpers.facility_profiles import (
    FACILITY_PROFILES,
    get_facility_reprocessing_tax,
)
from industry.helpers.loyalty_store import (
    get_offer_for_blueprint_type,
    navy_bpc_cost_for_plan,
    resolve_isk_per_lp,
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
        "(live ESI cost indices); optional compressed-ore conversion. "
        "Anonymous callers get max-skill refine assumptions; character_id "
        "requires authentication."
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
    type_ids = list(plan.leaf_materials.keys())
    prices = {
        tid: float(avg or 0.0)
        for tid, avg in EveMarketPrice.objects.filter(
            eve_type_id__in=type_ids
        ).values_list("eve_type_id", "average_price")
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
    compressed_payload = {
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
        "mineral_imports": dict(ore_plan.mineral_imports),
        "pi_other_imports": dict(ore_plan.pi_other_imports),
        "ice_imports": dict(ore_plan.ice_imports),
        "other_imports": dict(ore_plan.other_imports),
        "expected_minerals": dict(ore_plan.expected_minerals),
        "mineral_delta": dict(ore_plan.mineral_delta),
        "character_skills": (
            _character_skills_payload(skills) if skills else None
        ),
        "ore_yields": ore_refine_yields_payload(ore_yields),
    }
    return compressed_payload, ore_plan


def _plan_response_body(
    plan,
    leaf_materials,
    total_buy,
    materials_tsv,
    compressed_payload,
    ore_plan,
    navy_bpc=None,
):
    navy_bpc_isk = navy_bpc.total_isk if navy_bpc is not None else 0
    cost_breakdown = build_plan_cost_breakdown(
        plan,
        compressed_ore=ore_plan,
        navy_bpc_isk=navy_bpc_isk,
    )
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
        "leaf_materials": leaf_materials,
        "estimated_materials_buy_isk": total_buy,
        "materials_tsv": materials_tsv,
        "compressed_ore": compressed_payload,
        "cost_breakdown": cost_breakdown.to_dict(),
        "navy_bpc": navy_bpc.to_dict() if navy_bpc is not None else None,
    }


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

    Returns ((key, eve_type, character, me, te, exclude_type_ids), None)
    or (None, (status, ErrorResponse)).
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

    return (key, eve_type, character, me, te, exclude_type_ids), None


def _execute_plan_build(eve_type, payload, key, me, te, exclude_type_ids):
    try:
        return plan_build(
            eve_type,
            quantity=payload.quantity,
            blueprint_me=me,
            blueprint_te=te,
            facility=key,
            build_fuel_blocks=payload.build_fuel_blocks,
            exclude_type_ids=exclude_type_ids,
        )
    except ValueError as exc:
        msg = str(exc)
        if "cost index" in msg.lower() or "esi" in msg.lower():
            return 502, ErrorResponse(detail=msg)
        return 400, ErrorResponse(detail=msg)


def post_plan(request, payload: PlanRequestSchema):
    resolved, error = _resolve_plan_request(request, payload)
    if error is not None:
        return error
    key, eve_type, character, me, te, exclude_type_ids = resolved

    plan = _execute_plan_build(
        eve_type, payload, key, me, te, exclude_type_ids
    )
    if isinstance(plan, tuple):
        return plan

    leaf_materials, total_buy = _leaf_materials_with_prices(plan)
    materials_tsv = _leaf_materials_multibuy(leaf_materials)
    compressed_payload = None
    ore_plan = None

    if payload.compressed:
        result = _build_compressed_ore_section(plan, key, character, payload)
        if isinstance(result[1], ErrorResponse):
            return result
        compressed_payload, ore_plan = result
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
    )
