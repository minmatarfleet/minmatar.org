"""POST /{fleet_id}/fights/segments — save a battle report window."""

from authentication import AuthBearer

from fleets.endpoints.schemas import (
    FleetBattleSegment,
    FleetBattleSegmentRequest,
)
from fleets.helpers.fights.segments import fc_fleet, save_segment

PATH = "/{fleet_id}/fights/segments"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: FleetBattleSegment, 403: None, 404: None},
    "description": (
        "Save a window of the fleet's battle report under a name, for "
        "everyone who can see the report. The fleet's FC only. A blank name "
        "saves the window's EVE times, e.g. 18:27–18:49 ET."
    ),
}


def create_fleet_battle_segment(
    request, fleet_id: int, payload: FleetBattleSegmentRequest
):
    fleet, error = fc_fleet(request, fleet_id)
    if error:
        return error
    return save_segment(
        fleet, payload.name, payload.start, payload.end, request.user
    )
