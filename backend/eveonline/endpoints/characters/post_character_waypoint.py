"""POST /{character_id}/waypoint - set a character's in-game destination."""

from django.core.cache import cache
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.client import (
    CHAR_ESI_SUSPENDED,
    NO_VALID_ACCESS_TOKEN,
    NO_VALID_ESI_TOKEN,
    EsiClient,
)
from eveonline.models import EveCharacter

PATH = "{int:character_id}/waypoint"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Set a character's in-game destination",
    "description": (
        "Sets the autopilot destination of one of the caller's characters "
        "(ESI POST /ui/autopilot/waypoint). Needs the Desktop scope group. "
        "The desktop app sends it only on the pilot's own click. 409 means "
        "the character's token lacks esi-ui.write_waypoint.v1."
    ),
    "auth": AuthBearer(),
    "response": {
        204: None,
        400: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
        429: ErrorResponse,
        502: ErrorResponse,
    },
}

# One click is one request; this only stops a stuck button from hammering ESI.
RATE_LIMIT = 20
RATE_WINDOW_SECONDS = 60

# Known space: solar systems and NPC stations. Structures need docking
# access ESI can't check, so they are not offered.
SOLAR_SYSTEM_IDS = range(30_000_000, 33_000_000)
STATION_IDS = range(60_000_000, 64_000_000)


class WaypointRequest(BaseModel):
    destination_id: int
    clear_other_waypoints: bool = True


def _rate_limited(user_id: int) -> bool:
    key = f"eveonline:waypoint:{user_id}"
    cache.add(key, 0, RATE_WINDOW_SECONDS)
    try:
        return cache.incr(key) > RATE_LIMIT
    except ValueError:
        return False


def post_character_waypoint(
    request, character_id: int, payload: WaypointRequest
):
    character = EveCharacter.objects.filter(
        character_id=character_id, user=request.user
    ).first()
    if character is None:
        return 404, ErrorResponse(detail="Character not found")
    destination = payload.destination_id
    if destination not in SOLAR_SYSTEM_IDS and destination not in STATION_IDS:
        return 400, ErrorResponse(detail="Not a solar system or station")
    if _rate_limited(request.user.id):
        return 429, ErrorResponse(detail="Too many waypoints, slow down")

    response = EsiClient(character).set_autopilot_waypoint(
        destination, payload.clear_other_waypoints
    )
    if response.success():
        return 204, None
    if response.response_code in (
        NO_VALID_ESI_TOKEN,
        NO_VALID_ACCESS_TOKEN,
        CHAR_ESI_SUSPENDED,
    ):
        return 409, ErrorResponse(
            detail=(
                f"Add the Desktop scopes to {character.character_name} "
                "on my.minmatar.org to set destinations"
            )
        )
    return 502, ErrorResponse(detail="EVE did not take the waypoint")
