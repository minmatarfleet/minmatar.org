"""GET /voice-options: where a fleet can talk, for the fleet form."""

from typing import List, Optional

from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.helpers.fleet_form_access import fleet_form_denied
from fleets.helpers.voice_channels import default_channel_id, voice_channels
from fleets.models import FleetVoiceOption


class FleetVoiceChannelResponse(BaseModel):
    # A string: Discord ids overflow a JavaScript number.
    id: str
    name: str
    # The Discord category it sits under; "" for none.
    category: str


class FleetVoiceOptionResponse(BaseModel):
    id: int
    name: str
    # "discord" or "mumble"
    kind: str
    is_default: bool
    # A Discord option's voice channels, in Discord's order. Empty for
    # Mumble, an option without a server, or Discord unreachable.
    channels: List[FleetVoiceChannelResponse] = []
    # The channel the form starts on.
    default_channel_id: Optional[str] = None


PATH = "/voice-options"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[FleetVoiceOptionResponse], 403: ErrorResponse},
    "description": (
        "The voice options the fleet form offers (active ones only), with "
        "each Discord option's voice channels. Same access as /types."
    ),
}


def get_fleet_voice_options(request):
    denied = fleet_form_denied(request.user)
    if denied:
        return denied
    default = FleetVoiceOption.default_option()
    out = []
    for option in FleetVoiceOption.objects.filter(is_active=True):
        channels = voice_channels(option) or []
        channel_id = default_channel_id(option, channels)
        out.append(
            FleetVoiceOptionResponse(
                id=option.id,
                name=option.name,
                kind=option.kind,
                is_default=bool(default and option.id == default.id),
                channels=[
                    FleetVoiceChannelResponse(
                        id=str(channel.id),
                        name=channel.name,
                        category=channel.category,
                    )
                    for channel in channels
                ],
                default_channel_id=str(channel_id) if channel_id else None,
            )
        )
    return out
