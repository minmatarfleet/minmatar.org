"""GET /training/doctrines/{doctrine_id}/{column} - one doctrine's ships for one role, and who flies each."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import DoctrineCellResponse

PATH = "/doctrines/{doctrine_id}/{column}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "One doctrine's ships for one role, and who flies each",
    "auth": AuthBearer(),
    "response": {200: DoctrineCellResponse, 404: ErrorResponse},
}


def get_doctrine(request, doctrine_id: int, column: str):
    try:
        return 200, training.doctrine_cell(request.user, doctrine_id, column)
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
