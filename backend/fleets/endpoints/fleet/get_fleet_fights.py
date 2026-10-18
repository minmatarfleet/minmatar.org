"""GET /{fleet_id}/fights — the fleet's killmails as a timeline of rounds."""

from authentication import AuthBearer

from fleets.endpoints.helpers import _fleet_authorized, _fleet_manager
from fleets.endpoints.schemas import EveFleetFightsResponse
from fleets.helpers.fights.serve import fights_response, may_view
from fleets.helpers.fights.timeline import is_live
from fleets.models import EveFleet, EveFleetInstance

PATH = "/{fleet_id}/fights"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: EveFleetFightsResponse, 403: None, 404: None},
    "description": (
        "Rounds of fighting, each with its kills, losses, who we fought and "
        "battle report links. Rebuilt every 30 s while the fleet is out and "
        "for two hours after. While the fleet is live only its managers and "
        "pilots may read it. status is building until the first build is "
        "done; ask again in a few seconds."
    ),
}


def get_fleet_fights(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if (
        not fleet
        or not EveFleetInstance.objects.filter(eve_fleet=fleet).exists()
    ):
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    manager = _fleet_manager(request, fleet)
    live = is_live(fleet)
    if not may_view(request.user, fleet, manager=manager, live=live):
        return 403, None
    return fights_response(fleet, can_edit=manager, live=live)
