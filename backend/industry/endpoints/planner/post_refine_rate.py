"""POST /refine-rate - resolve facility refine yield for character/implants."""

from app.errors import ErrorResponse
from authentication import AuthOptional
from eveonline.models import EveCharacter
from industry.endpoints.planner.auth_helpers import auth_required_for_character
from industry.endpoints.planner.schemas import (
    RefineRateRequestSchema,
    RefineRateResponseSchema,
)
from industry.helpers.facility_profiles import FACILITY_PROFILES
from industry.helpers.reprocessing_skills import (
    compression_ore_refine_yields,
    ore_refine_yields_payload,
    resolve_refine_rate,
)

PATH = "refine-rate"
METHOD = "post"
ROUTE_SPEC = {
    "summary": (
        "Resolve reprocessing yield for a facility using optional character "
        "skills and implant toggle (no full build plan). Anonymous callers "
        "get max-skill assumptions; character_id requires authentication."
    ),
    "auth": AuthOptional(),
    "response": {
        200: RefineRateResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
    },
}


def _skills_payload(skills) -> dict:
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


def post_refine_rate(request, payload: RefineRateRequestSchema):
    key = payload.facility_key.lower().strip()
    if key not in FACILITY_PROFILES:
        return 400, ErrorResponse(
            detail=f"Unknown facility {payload.facility_key!r}"
        )

    auth_error = auth_required_for_character(request, payload.character_id)
    if auth_error is not None:
        return auth_error

    character = None
    if payload.character_id is not None:
        character = EveCharacter.objects.filter(
            character_id=payload.character_id
        ).first()
        if character is None:
            return 400, ErrorResponse(
                detail=f"Unknown character_id {payload.character_id}"
            )

    try:
        rate, source, skills = resolve_refine_rate(
            key,
            character=character,
            use_reprocessing_implants=payload.use_reprocessing_implants,
            refine_rate_override=payload.refine_rate,
        )
        ore_yields = compression_ore_refine_yields(
            key,
            skills=skills,
            use_reprocessing_implants=payload.use_reprocessing_implants,
            refine_rate_override=payload.refine_rate,
        )
    except ValueError as exc:
        return 400, ErrorResponse(detail=str(exc))

    return {
        "facility_key": key,
        "refine_rate": rate,
        "refine_rate_source": source,
        "character_skills": _skills_payload(skills) if skills else None,
        "ore_yields": ore_refine_yields_payload(ore_yields),
    }
