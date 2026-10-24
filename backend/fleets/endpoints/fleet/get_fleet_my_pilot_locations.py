"""GET /{fleet_id}/my-pilot-locations — where the caller's characters are, for form-up."""

from typing import List, Optional

from pydantic import BaseModel

from authentication import AuthBearer
from eveonline.helpers.characters import user_characters

from fleets.endpoints.helpers import _fleet_authorized
from fleets.helpers.pilot_locations import pilot_locations
from fleets.models import EveFleet

PATH = "/{fleet_id}/my-pilot-locations"
METHOD = "get"


class MyPilotLocationResponse(BaseModel):
    character_id: int
    character_name: str
    solar_system_id: Optional[int] = None
    solar_system_name: Optional[str] = None
    station_id: Optional[int] = None
    structure_id: Optional[int] = None
    has_location_scope: bool


ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[MyPilotLocationResponse], 403: None, 404: None},
    "description": (
        "Where each of the caller's characters is (ESI location, cached for "
        "a minute). has_location_scope is false when the character's token "
        "lacks esi-location.read_location.v1 (the Desktop scope group); the "
        "location is null then, and also when ESI fails for that character."
    ),
}


def get_fleet_my_pilot_locations(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None

    characters = user_characters(request.user).order_by("character_name")
    return [
        MyPilotLocationResponse(**row) for row in pilot_locations(characters)
    ]
