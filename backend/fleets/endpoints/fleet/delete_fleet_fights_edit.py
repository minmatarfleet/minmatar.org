"""DELETE /{fleet_id}/fights/edits/{edit_id} — undo one merge or split."""

from authentication import AuthBearer

from fleets.endpoints.schemas import EveFleetFightsResponse
from fleets.helpers.fights import timeline as fights
from fleets.helpers.fights.serve import editable_fleet, recut_response

PATH = "/{fleet_id}/fights/edits/{edit_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: EveFleetFightsResponse, 403: None, 404: None},
    "description": (
        "Undo one merge or split. Fleet managers only; returns the re-cut "
        "timeline."
    ),
}


def undo_fleet_fights_edit(request, fleet_id: int, edit_id: int):
    fleet, error = editable_fleet(request, fleet_id)
    if error:
        return error
    if not fights.undo(fleet, edit_id):
        return 404, None
    return recut_response(fleet)
