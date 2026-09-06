"""GET /{fleet_id}/ship-volunteers — list who can fly which doctrine fit."""

from typing import List

from authentication import AuthBearer

from fleets.endpoints.helpers import (
    _fleet_authorized,
    make_ship_volunteer_response,
)
from fleets.endpoints.schemas import EveFleetShipVolunteerResponse
from fleets.models import EveFleet, EveFleetShipVolunteer

PATH = "/{fleet_id}/ship-volunteers"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: List[EveFleetShipVolunteerResponse],
        403: None,
        404: None,
    },
    "description": "List ship volunteers for a fleet. Same auth as get fleet.",
}


def get_fleet_ship_volunteers(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    volunteers = (
        EveFleetShipVolunteer.objects.filter(eve_fleet=fleet)
        .select_related("fitting", "fleet_fitting")
        .order_by("fitting_id", "fleet_fitting_id", "id")
    )
    return [make_ship_volunteer_response(v) for v in volunteers]
