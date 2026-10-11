"""POST /npsi-events/{event_id}/discord-preping — Discord pre-ping button."""

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.endpoints.npsi.auth import authorize_request, load_event
from fleets.endpoints.npsi.schemas import (
    DiscordNpsiActionRequest,
    DiscordNpsiActionResponse,
)
from fleets.helpers.npsi_actions import NpsiActionError, preping_event

PATH = "/npsi-events/{event_id}/discord-preping"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Send a fleet pre-ping from an NPSI Discord button",
    "auth": AuthBearer(),
    "response": {
        200: DiscordNpsiActionResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        500: ErrorResponse,
    },
}


def post_npsi_discord_preping(
    request, event_id: int, payload: DiscordNpsiActionRequest
):
    try:
        event = load_event(event_id)
        authorize_request(request, event, payload.discord_user_id)
        preping_event(event)
    except NpsiActionError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    return 200, DiscordNpsiActionResponse(
        event_id=event.id,
        status=event.status,
        fleet_id=event.eve_fleet_id,
    )
