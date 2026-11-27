"""PUT /corporations/{corporation_id}/discord/fleet-follows/{tribe_group_id}
- ask to get a tribe group's fleet posts in a channel of the corporation's
Discord. It forwards once one of the group's chiefs approved it."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import (
    CorporationFleetFollows,
    CorporationFleetFollowUpdate,
)
from eveonline.helpers.corporations.fleet_follows import (
    FollowError,
    save_follow,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord/fleet-follows/{tribe_group_id}"
METHOD = "put"
ROUTE_SPEC = {
    "response": {
        200: CorporationFleetFollows,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": (
        "Ask for a tribe group's fleet posts in a channel of this "
        "corporation's Discord (CEO and directors)"
    ),
    "description": (
        "A new follow, or a new channel, waits for a group chief's "
        "approval. Errors: not_eligible (not an Alliance or Associate "
        "corporation), not_connected (the bot isn't in the server), "
        "unknown_channel, discord_unreachable, unknown_group (404)."
    ),
}


def put_corporation_fleet_follow(
    request,
    corporation_id: int,
    tribe_group_id: int,
    payload: CorporationFleetFollowUpdate,
):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    try:
        return save_follow(
            corporation, tribe_group_id, payload.channel_id, request.user
        )
    except FollowError as error:
        return error.status, ErrorResponse(detail=error.code)
