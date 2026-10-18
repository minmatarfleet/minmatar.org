"""POST /{fleet_id}/fights/merge — merge every round between two times."""

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.endpoints.schemas import (
    EveFleetFightsResponse,
    FleetFightMergeRequest,
)
from fleets.helpers.fights import timeline as fights
from fleets.helpers.fights.serve import editable_fleet, recut_response

PATH = "/{fleet_id}/fights/merge"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetFightsResponse,
        400: ErrorResponse,
        403: None,
        404: None,
    },
    "description": (
        "Merge every round between start (the first mail of the first round) "
        "and end (the last mail of the last) into one. Replaces any split "
        "inside. Fleet managers only; returns the re-cut timeline."
    ),
}


def merge_fleet_fights(
    request, fleet_id: int, payload: FleetFightMergeRequest
):
    fleet, error = editable_fleet(request, fleet_id)
    if error:
        return error
    if payload.end <= payload.start:
        return 400, ErrorResponse(detail="end must be after start")
    fights.merge(fleet, payload.start, payload.end, request.user)
    return recut_response(fleet)
