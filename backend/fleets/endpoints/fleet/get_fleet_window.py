"""GET /{fleet_id}/window — the desktop app's fleet window in one read."""

from authentication import AuthBearer

from fleets.endpoints.helpers import _fleet_authorized, etag_json_response
from fleets.endpoints.schemas import FleetWindowResponse
from fleets.helpers.fleet_window import fleet_window
from fleets.models import EveFleet

PATH = "/{fleet_id}/window"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: FleetWindowResponse, 304: None, 403: None, 404: None},
    "description": (
        "Everything the desktop fleet window shows: the fleet, doctrine "
        "ships flying vs signed up, uncovered roles, kill totals and the "
        "caller's own characters. Only the fleet's FC gets the roster and "
        "the pilots that need attention. Sends an ETag; a matching "
        "If-None-Match gets 304."
    ),
}


def get_fleet_window(request, fleet_id: int):
    fleet = (
        EveFleet.objects.select_related("doctrine", "location")
        .filter(id=fleet_id)
        .first()
    )
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    return etag_json_response(
        request, FleetWindowResponse(**fleet_window(fleet, request.user))
    )
