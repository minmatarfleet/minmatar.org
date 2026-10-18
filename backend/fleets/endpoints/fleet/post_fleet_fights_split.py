"""POST /{fleet_id}/fights/split — start a new round at a time."""

from authentication import AuthBearer

from fleets.endpoints.schemas import (
    EveFleetFightsResponse,
    FleetFightSplitRequest,
)
from fleets.helpers.fights import timeline as fights
from fleets.helpers.fights.serve import editable_fleet, recut_response

PATH = "/{fleet_id}/fights/split"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: EveFleetFightsResponse, 403: None, 404: None},
    "description": (
        "Start a new round at a time, usually the first mail after a quiet "
        "gap. Fleet managers only; returns the re-cut timeline."
    ),
}


def split_fleet_fights(
    request, fleet_id: int, payload: FleetFightSplitRequest
):
    fleet, error = editable_fleet(request, fleet_id)
    if error:
        return error
    fights.split(fleet, payload.at, request.user)
    return recut_response(fleet)
