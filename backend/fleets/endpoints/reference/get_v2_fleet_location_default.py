"""GET /v2/locations/default — where a flash form forms up by default."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature

from fleets.endpoints.schemas import EveFleetLocationDefaultResponse
from fleets.helpers.fleet_location import default_form_up_location

PATH = "/v2/locations/default"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetLocationDefaultResponse,
        403: ErrorResponse,
    },
    "description": (
        "The form-up location one of your characters is docked at (main "
        "first, ESI location cached for a minute), else the staging. "
        "Needs fleets.create."
    ),
}


def get_v2_fleet_location_default(request):
    denied = require_feature(request.user, "fleets.create")
    if denied:
        return denied
    location = default_form_up_location(request.user)
    return EveFleetLocationDefaultResponse(
        location_id=location.location_id if location else None
    )
