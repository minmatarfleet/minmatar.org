"""GET /{fleet_id}/refits — FC-configured refits for the fleet's doctrine fits."""

from typing import List

from authentication import AuthBearer

from fleets.endpoints.helpers import (
    _fleet_authorized,
    make_fleet_refit_response,
)
from fleets.endpoints.schemas import EveFleetFittingRefitResponse
from fleets.models import EveFleet, EveFleetFittingRefit

PATH = "/{fleet_id}/refits"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: List[EveFleetFittingRefitResponse],
        403: None,
        404: None,
    },
    "description": "List fleet refits (cargo to carry per doctrine fit). Same auth as get fleet.",
}


def get_fleet_refits(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    refits = (
        EveFleetFittingRefit.objects.filter(eve_fleet=fleet)
        .select_related("fitting", "fleet_fitting")
        .order_by("fitting_id", "fleet_fitting_id", "id")
    )
    return [make_fleet_refit_response(r) for r in refits]
