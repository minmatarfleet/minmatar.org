"""GET /voice-options: where a fleet can talk, for the fleet form."""

from typing import List

from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.helpers.fleet_form_access import fleet_form_denied
from fleets.models import FleetVoiceOption


class FleetVoiceOptionResponse(BaseModel):
    id: int
    name: str
    # "discord" or "mumble"
    kind: str
    is_default: bool


PATH = "/voice-options"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[FleetVoiceOptionResponse], 403: ErrorResponse},
    "description": (
        "The voice options the fleet form offers (active ones only). "
        "Same access as /types."
    ),
}


def get_fleet_voice_options(request):
    denied = fleet_form_denied(request.user)
    if denied:
        return denied
    default = FleetVoiceOption.default_option()
    return [
        FleetVoiceOptionResponse(
            id=option.id,
            name=option.name,
            kind=option.kind,
            is_default=bool(default and option.id == default.id),
        )
        for option in FleetVoiceOption.objects.filter(is_active=True)
    ]
