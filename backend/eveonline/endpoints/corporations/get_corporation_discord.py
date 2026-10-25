"""GET /corporations/{corporation_id}/discord - the corp's Discord server."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import CorporationDiscordSettings
from eveonline.helpers.corporations.discord_invite import discord_settings
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord"
METHOD = "get"
ROUTE_SPEC = {
    "response": {
        200: CorporationDiscordSettings,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "The corporation's Discord server (CEO and directors)",
}


def get_corporation_discord(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    return discord_settings(corporation)
