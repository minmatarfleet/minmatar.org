"""GET /types — fleet type enum values for fleet creation UI."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.endpoints.schemas import EveFleetType

PATH = "/types"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetType], 403: ErrorResponse},
}


def get_fleet_types(request):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}
    return [
        EveFleetType.STRATEGIC,
        EveFleetType.NON_STRATEGIC,
        EveFleetType.TRAINING,
    ]
