"""DELETE /{fleet_id}/role-volunteers/{volunteer_id} — remove own signup."""

from authentication import AuthBearer
from eveonline.helpers.characters import user_characters

from fleets.endpoints.helpers import _fleet_authorized
from fleets.models import EveFleet, EveFleetRoleVolunteer

PATH = "/{fleet_id}/role-volunteers/{volunteer_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {204: None, 403: None, 404: None},
    "description": "Remove a role volunteer. Volunteer must belong to the current user's character.",
}


def delete_fleet_role_volunteer(request, fleet_id: int, volunteer_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    volunteer = EveFleetRoleVolunteer.objects.filter(
        id=volunteer_id, eve_fleet=fleet
    ).first()
    if not volunteer:
        return 404, None
    allowed_ids = [c.character_id for c in user_characters(request.user)]
    if volunteer.character_id not in allowed_ids:
        return 403, None
    volunteer.delete()
    return 204, None
