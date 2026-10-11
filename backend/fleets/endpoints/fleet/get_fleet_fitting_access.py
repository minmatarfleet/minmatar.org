"""GET /{fleet_id}/fitting-access — can the FC save refits/custom fits in-game?"""

from authentication import AuthBearer

from fleets.endpoints.helpers import _fleet_authorized, _fleet_manager
from fleets.endpoints.schemas import EveFleetFittingAccessResponse
from fleets.helpers.esi_fittings import fitting_access
from fleets.models import EveFleet

PATH = "/{fleet_id}/fitting-access"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: EveFleetFittingAccessResponse, 403: None, 404: None},
    "description": (
        "Whether the requesting fleet manager has a character with the "
        "esi-fittings.write_fittings.v1 scope (needed to save refits and "
        "custom fits in-game), plus which character to prompt for the "
        "Fleet Commander token."
    ),
}


def get_fleet_fitting_access(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    if not _fleet_manager(request, fleet):
        return 403, None
    return 200, EveFleetFittingAccessResponse(**fitting_access(request.user))
