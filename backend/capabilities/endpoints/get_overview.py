"""GET /training - your characters: ships they fly, the ship each trains for, ready ships per role."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import TrainingOverviewResponse

PATH = "/"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Your characters: ships they fly, the ship each trains for, ready ships per role",
    "auth": AuthBearer(),
    "response": {200: TrainingOverviewResponse, 404: ErrorResponse},
}


def get_overview(request):
    try:
        return 200, training.overview(request.user)
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
