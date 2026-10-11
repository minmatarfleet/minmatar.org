"""DELETE /{fleet_id}/ship-volunteers/{volunteer_id} — remove a ship signup."""

from authentication import AuthBearer
from eveonline.helpers.characters import user_characters

from fleets.endpoints.helpers import _fleet_authorized, _fleet_manager
from fleets.models import EveFleet, EveFleetShipVolunteer

PATH = "/{fleet_id}/ship-volunteers/{volunteer_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {204: None, 403: None, 404: None},
    "description": (
        "Remove a ship volunteer. Must be the volunteer's own character "
        "or the fleet commander."
    ),
}


def delete_fleet_ship_volunteer(request, fleet_id: int, volunteer_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    volunteer = EveFleetShipVolunteer.objects.filter(
        id=volunteer_id, eve_fleet=fleet
    ).first()
    if not volunteer:
        return 404, None
    allowed_ids = [c.character_id for c in user_characters(request.user)]
    if volunteer.character_id not in allowed_ids and not _fleet_manager(
        request, fleet
    ):
        return 403, None
    volunteer.delete()
    return 204, None
