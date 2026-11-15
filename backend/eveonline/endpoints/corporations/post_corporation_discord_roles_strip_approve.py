"""POST /corporations/{corporation_id}/discord/roles/strip/approve - go ahead."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.guild_departures import StripError, approve_strip_hold
from eveonline.endpoints.corporations.schemas import CorporationDiscordSettings
from eveonline.helpers.corporations.discord_bot import (
    corporation_discord_settings,
    is_connected,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord/roles/strip/approve"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        200: CorporationDiscordSettings,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": (
        "Approve a held pass that would remove all roles from many people "
        "at once (CEO and directors)"
    ),
}


def post_corporation_discord_roles_strip_approve(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    if not is_connected(corporation) or corporation.discord_guild is None:
        return 400, ErrorResponse(detail="not_connected")
    try:
        approve_strip_hold(corporation.discord_guild)
    except StripError as error:
        return 400, ErrorResponse(detail=error.code)
    return corporation_discord_settings(corporation)
