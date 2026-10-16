"""GET /{fleet_id}/kills — what a tracked fleet killed and lost."""

from authentication import AuthBearer
from feed.helpers.fleet_kills import fleet_kill_report

from fleets.endpoints.helpers import _fleet_authorized
from fleets.endpoints.schemas import EveFleetKillsResponse
from fleets.models import EveFleet

PATH = "/{fleet_id}/kills"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: EveFleetKillsResponse, 403: None, 404: None},
    "description": (
        "Killmails the fleet's pilots were on while in fleet, from the feed. "
        "Totals count capsules towards ISK but not ships."
    ),
}


def get_fleet_kills(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    return fleet_kill_report(fleet)
