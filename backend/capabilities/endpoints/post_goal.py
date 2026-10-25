"""POST /training/characters/{character_id}/goals - add a doctrine fit to a character's training queue."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import GoalRequest, TrainingChangeResponse

PATH = "/characters/{character_id}/goals"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Add a doctrine fit to a character's training queue",
    "auth": AuthBearer(),
    "response": {200: TrainingChangeResponse, 404: ErrorResponse},
}


def post_goal(request, character_id: int, payload: GoalRequest):
    try:
        training.add_goal(request.user, character_id, payload.fitting_id)
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
    return 200, TrainingChangeResponse(ok=True)
