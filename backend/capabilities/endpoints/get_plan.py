"""GET /training/characters/{character_id}/plans/{fitting_id} - the skills a character needs for one doctrine fit, in training order."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import TrainingPlanResponse

PATH = "/characters/{character_id}/plans/{fitting_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "The skills a character needs for one doctrine fit, in training order",
    "auth": AuthBearer(),
    "response": {200: TrainingPlanResponse, 404: ErrorResponse},
}


def get_plan(request, character_id: int, fitting_id: int):
    try:
        return 200, training.plan_view(request.user, character_id, fitting_id)
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
