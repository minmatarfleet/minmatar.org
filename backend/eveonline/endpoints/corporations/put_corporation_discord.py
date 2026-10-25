"""PUT /corporations/{corporation_id}/discord - set the corp's Discord invite."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import (
    CorporationDiscordInviteRequest,
    CorporationDiscordSettings,
)
from eveonline.helpers.corporations.discord_invite import (
    DiscordInviteError,
    discord_settings,
    save_discord_invite,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord"
METHOD = "put"
ROUTE_SPEC = {
    "response": {
        200: CorporationDiscordSettings,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Set the corporation's Discord invite (CEO and directors)",
}


def put_corporation_discord(
    request, corporation_id: int, payload: CorporationDiscordInviteRequest
):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    try:
        save_discord_invite(corporation, payload.invite_url)
    except DiscordInviteError as e:
        return 400, ErrorResponse(detail=e.code)
    return discord_settings(corporation)
