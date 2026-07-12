"""GET /types — fleet type enum values for fleet creation UI."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature

from fleets.endpoints.schemas import EveFleetType

PATH = "/types"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetType], 403: ErrorResponse},
}


def get_fleet_types(request):
    denied = require_feature(request.user, "fleets.create")
    if denied:
        return denied
    return [
        EveFleetType.STRATEGIC,
        EveFleetType.NON_STRATEGIC,
        EveFleetType.TRAINING,
    ]
