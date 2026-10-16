"""GET /window/current — the fleet window for the fleet the user is in."""

from authentication import AuthBearer

from fleets.endpoints.helpers import _fleet_authorized, etag_json_response
from fleets.endpoints.schemas import (
    CurrentFleetWindowResponse,
    FleetWindowResponse,
)
from fleets.helpers.fleet_window import current_window_fleet_id, fleet_window
from fleets.models import EveFleet

PATH = "/window/current"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: CurrentFleetWindowResponse, 304: None},
    "description": (
        "The desktop fleet window for the fleet the user commands or has a "
        "character in right now (or, for its FC, one that closed in the "
        "last few hours); window is null when there is none. Read from the "
        "tracked fleet, not ESI, so it is cheap to poll. Sends an ETag; a "
        "matching If-None-Match gets 304."
    ),
}


def get_current_fleet_window(request):
    window = None
    fleet_id = current_window_fleet_id(request.user)
    if fleet_id:
        fleet = (
            EveFleet.objects.select_related("doctrine", "location")
            .filter(id=fleet_id)
            .first()
        )
        if fleet and _fleet_authorized(request, fleet):
            window = FleetWindowResponse(**fleet_window(fleet, request.user))
    return etag_json_response(
        request, CurrentFleetWindowResponse(window=window)
    )
