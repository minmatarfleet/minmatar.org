"""GET /{fleet_id}/role-volunteers — list role signups."""

from typing import List

from authentication import AuthBearer

from fleets.endpoints.helpers import _fleet_authorized
from fleets.endpoints.schemas import EveFleetRoleVolunteerResponse
from fleets.models import EveFleet, EveFleetRoleVolunteer

PATH = "/{fleet_id}/role-volunteers"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: List[EveFleetRoleVolunteerResponse],
        403: None,
        404: None,
    },
    "description": "List role volunteers for a fleet. Same auth as get fleet.",
}


def get_fleet_role_volunteers(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    volunteers = EveFleetRoleVolunteer.objects.filter(
        eve_fleet=fleet
    ).order_by("role", "id")
    return [
        EveFleetRoleVolunteerResponse(
            id=v.id,
            character_id=v.character_id,
            character_name=v.character_name,
            role=v.role,
            subtype=v.subtype,
            quantity=v.quantity,
        )
        for v in volunteers
    ]
