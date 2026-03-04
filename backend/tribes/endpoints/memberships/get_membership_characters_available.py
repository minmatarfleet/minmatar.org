"""GET "/{tribe_id}/groups/{group_id}/memberships/characters-available" - your characters and whether they qualify."""

from typing import List

from authentication import AuthBearer
from eveonline.models import EveCharacter
from tribes.endpoints.memberships.schemas import (
    AvailableCharacterSchema,
    RequirementQualificationSchema,
)
from tribes.helpers.requirements import check_character_meets_requirements
from tribes.models import TribeGroup

PATH = "/{tribe_id}/groups/{group_id}/memberships/characters-available"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List your characters and whether their assets/skills qualify for this group (owner only).",
    "response": {200: List[AvailableCharacterSchema], 404: dict},
    "auth": AuthBearer(),
}


def _build_available_character_schema(
    character, tg
) -> AvailableCharacterSchema:
    """Build AvailableCharacterSchema for one character and tribe group."""
    req_snapshot = check_character_meets_requirements(character, tg)
    requirements = [
        RequirementQualificationSchema(
            requirement_id=rid,
            display=data["display"],
            met=data["met"],
            detail=data["detail"],
        )
        for rid, data in req_snapshot.items()
    ]
    qualifies = any(data["met"] for data in req_snapshot.values())
    missing_skills = any(
        data.get("skill_met") is False for data in req_snapshot.values()
    )
    missing_assets = any(
        data.get("asset_met") is False for data in req_snapshot.values()
    )
    return AvailableCharacterSchema(
        character_id=character.character_id,
        character_name=character.character_name,
        qualifies=qualifies,
        requirements=requirements,
        missing_skills=missing_skills,
        missing_assets=missing_assets,
    )


def get_membership_characters_available(request, tribe_id: int, group_id: int):
    tg = (
        TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id)
        .prefetch_related(
            "requirements__asset_types__eve_type",
            "requirements__qualifying_skills__eve_type",
        )
        .first()
    )
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    characters = EveCharacter.objects.filter(user=request.user).order_by(
        "character_name"
    )
    return 200, [_build_available_character_schema(c, tg) for c in characters]
