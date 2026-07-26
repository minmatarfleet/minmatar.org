"""GET /audiences — Discord audiences for fleet pings."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature

from fleets.endpoints.schemas import EveFleetChannelResponse
from fleets.models import EveFleetAudience

PATH = "/audiences"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetChannelResponse], 403: ErrorResponse},
}


def get_fleet_audiences(request):
    denied = require_feature(request.user, "fleets.create")
    if denied:
        return denied
    audiences = EveFleetAudience.objects.filter(hidden=False).all()
    response = []
    for audience in audiences:
        response.append(
            {
                "id": audience.id,
                "display_name": audience.name,
                "display_channel_name": audience.discord_channel_name,
                "image_url": audience.image_url,
            }
        )
    return response
