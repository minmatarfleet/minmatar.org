"""DELETE /training/characters/{character_id}/goals/{fitting_id} - take a ship off a character's training queue."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import TrainingChangeResponse

PATH = "/characters/{character_id}/goals/{fitting_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Take a ship off a character's training queue",
    "auth": AuthBearer(),
    "response": {200: TrainingChangeResponse, 404: ErrorResponse},
}


def delete_goal(request, character_id: int, fitting_id: int):
    try:
        training.remove_goal(request.user, character_id, fitting_id)
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
    return 200, TrainingChangeResponse(ok=True)
