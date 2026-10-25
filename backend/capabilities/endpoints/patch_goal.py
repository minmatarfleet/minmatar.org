"""PATCH /training/characters/{character_id}/goals/{fitting_id} - train a ship first, or change how far to train it."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import (
    GoalPatchRequest,
    TrainingChangeResponse,
)

PATH = "/characters/{character_id}/goals/{fitting_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Train a ship first, or change how far to train it",
    "auth": AuthBearer(),
    "response": {200: TrainingChangeResponse, 404: ErrorResponse},
}


def patch_goal(
    request, character_id: int, fitting_id: int, payload: GoalPatchRequest
):
    try:
        training.update_goal(
            request.user,
            character_id,
            fitting_id,
            first=payload.first,
            target=payload.target,
        )
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
    return 200, TrainingChangeResponse(ok=True)
