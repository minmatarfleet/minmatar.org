"""GET /corporations/{corporation_id}/discord/fleet-follows - the tribe
groups whose fleet posts the corporation's Discord gets."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import CorporationFleetFollows
from eveonline.helpers.corporations.fleet_follows import (
    fleet_follows_response,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord/fleet-follows"
METHOD = "get"
ROUTE_SPEC = {
    "response": {
        200: CorporationFleetFollows,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": (
        "Tribe groups whose fleet posts go to this corporation's Discord "
        "(CEO and directors)"
    ),
}


def get_corporation_fleet_follows(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    return fleet_follows_response(corporation)
