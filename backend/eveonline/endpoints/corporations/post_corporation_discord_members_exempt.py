"""POST /corporations/{corporation_id}/discord/members/exempt - keep one."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.guild_access import AccessError, exempt_pending
from eveonline.endpoints.corporations.schemas import (
    CorporationDiscordSettings,
    DiscordMemberExemptRequest,
)
from eveonline.helpers.corporations.discord_bot import (
    corporation_discord_settings,
    is_connected,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord/members/exempt"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        200: CorporationDiscordSettings,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Exempt someone on the pending removal list (CEO and directors)",
}


def post_corporation_discord_members_exempt(
    request, corporation_id: int, payload: DiscordMemberExemptRequest
):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    if not is_connected(corporation) or corporation.discord_guild is None:
        return 400, ErrorResponse(detail="not_connected")
    try:
        discord_id = int(payload.discord_id)
    except ValueError:
        return 400, ErrorResponse(detail="not_pending")
    try:
        exempt_pending(corporation.discord_guild, discord_id, request.user)
    except AccessError as error:
        return 400, ErrorResponse(detail=error.code)
    return corporation_discord_settings(corporation)
