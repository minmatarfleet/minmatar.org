"""GET /current — in-game fleets for the user's characters (ESI)."""

from typing import List

from authentication import AuthBearer
from eveonline.client import EsiClient
from eveonline.helpers.characters import user_characters

from fleets.endpoints.schemas import UserActiveFleetResponse

PATH = "/current"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get the fleets that the user is currently active in",
    "auth": AuthBearer(),
    "response": {200: List[UserActiveFleetResponse], 403: None, 404: None},
}


def get_user_active_fleets(request):
    active_fleets = []
    for char in user_characters(request.user):
        response = EsiClient(char).get_active_fleet()
        if response.success():
            active_fleets.append(
                UserActiveFleetResponse(
                    character_id=char.character_id,
                    eve_fleet_id=response.data["fleet_id"],
                    fleet_boss_id=response.data["fleet_boss_id"],
                    fleet_role=response.data["role"],
                )
            )
    return active_fleets
