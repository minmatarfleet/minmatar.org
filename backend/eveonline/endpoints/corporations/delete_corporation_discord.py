"""DELETE /corporations/{corporation_id}/discord - remove the corp's Discord."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import CorporationDiscordSettings
from eveonline.helpers.corporations.discord_bot import (
    corporation_discord_settings,
)
from eveonline.helpers.corporations.discord_invite import (
    remove_discord_invite,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord"
METHOD = "delete"
ROUTE_SPEC = {
    "response": {
        200: CorporationDiscordSettings,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Remove the corporation's Discord server (CEO and directors)",
}


def delete_corporation_discord(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    remove_discord_invite(corporation)
    return corporation_discord_settings(corporation)
