"""PATCH /training/characters/{character_id} - mark one of your characters as not for fleets (or for fleets again)."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import (
    CharacterPatchRequest,
    TrainingChangeResponse,
)

PATH = "/characters/{character_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Mark one of your characters as not for fleets (or for fleets again)",
    "auth": AuthBearer(),
    "response": {200: TrainingChangeResponse, 404: ErrorResponse},
}


def patch_character(
    request, character_id: int, payload: CharacterPatchRequest
):
    try:
        training.set_not_for_fleets(
            request.user, character_id, payload.not_for_fleets
        )
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
    return 200, TrainingChangeResponse(ok=True)
