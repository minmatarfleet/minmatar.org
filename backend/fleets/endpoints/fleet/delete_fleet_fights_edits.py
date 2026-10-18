"""DELETE /{fleet_id}/fights/edits — back to the automatic rounds."""

from authentication import AuthBearer

from fleets.endpoints.schemas import EveFleetFightsResponse
from fleets.helpers.fights import timeline as fights
from fleets.helpers.fights.serve import editable_fleet, recut_response

PATH = "/{fleet_id}/fights/edits"
METHOD = "delete"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: EveFleetFightsResponse, 403: None, 404: None},
    "description": (
        "Drop every merge and split. Fleet managers only; returns the "
        "re-cut timeline."
    ),
}


def reset_fleet_fights(request, fleet_id: int):
    fleet, error = editable_fleet(request, fleet_id)
    if error:
        return error
    fights.undo(fleet, None)
    return recut_response(fleet)
