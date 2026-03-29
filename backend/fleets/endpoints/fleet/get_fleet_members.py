"""GET /{fleet_id}/members — tracked fleet members from last instance."""

from typing import List

from authentication import AuthBearer

from fleets.endpoints.schemas import EveFleetMemberResponse
from fleets.models import EveFleet, EveFleetInstanceMember

PATH = "/{fleet_id}/members"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetMemberResponse], 403: None, 404: None},
    "description": "Get fleet members. Requires fleets.view_evefleet.",
}


def get_fleet_members(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not request.user.has_perm("fleets.view_evefleet"):
        return 403, None

    response = []
    for member in EveFleetInstanceMember.objects.filter(
        eve_fleet_instance__eve_fleet=fleet
    ):
        response.append(
            {
                "character_id": member.character_id,
                "character_name": member.character_name,
                "ship_type_id": member.ship_type_id,
                "ship_type_name": member.ship_name,
                "solar_system_id": member.solar_system_id,
                "solar_system_name": member.solar_system_name,
            }
        )

    return response
