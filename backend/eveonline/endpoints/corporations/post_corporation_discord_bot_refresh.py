"""POST /corporations/{corporation_id}/discord/bot/refresh - try again."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import CorporationDiscordSettings
from eveonline.helpers.corporations.discord_bot import (
    corporation_discord_settings,
    is_connected,
    mark_pending,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation
from eveonline.tasks.corporations import refresh_corporation_discord_bot

PATH = "corporations/{corporation_id}/discord/bot/refresh"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        200: CorporationDiscordSettings,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Ask the bot to set up its invite again, after the server "
    "fixed its permissions (CEO and directors)",
}


def post_corporation_discord_bot_refresh(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    if not is_connected(corporation):
        return 400, ErrorResponse(detail="not_connected")
    mark_pending(corporation)
    # Queued copies of the same call collapse into one (AppTask dedupe).
    refresh_corporation_discord_bot.delay(corporation.corporation_id)
    return corporation_discord_settings(corporation)
