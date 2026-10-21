"""DELETE /{fleet_id}/fights/segments/{segment_id} — remove a saved window."""

from authentication import AuthBearer

from fleets.helpers.fights.segments import fc_fleet
from fleets.models import EveFleetBattleSegment

PATH = "/{fleet_id}/fights/segments/{segment_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {204: None, 403: None, 404: None},
    "description": "Remove a saved battle report window. The fleet's FC only.",
}


def delete_fleet_battle_segment(request, fleet_id: int, segment_id: int):
    fleet, error = fc_fleet(request, fleet_id)
    if error:
        return error
    deleted, _ = EveFleetBattleSegment.objects.filter(
        eve_fleet=fleet, id=segment_id
    ).delete()
    if not deleted:
        return 404, None
    return 204, None
