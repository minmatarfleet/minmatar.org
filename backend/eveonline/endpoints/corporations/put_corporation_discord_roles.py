"""PUT /corporations/{corporation_id}/discord/roles - map existing roles."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.guild_roles import (
    CORPORATION_STATES,
    MappingError,
    replace_role_mappings,
)
from eveonline.endpoints.corporations.schemas import (
    CorporationDiscordSettings,
    DiscordRoleMappingUpdate,
)
from eveonline.helpers.corporations.discord_bot import (
    corporation_discord_settings,
    is_connected,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

PATH = "corporations/{corporation_id}/discord/roles"
METHOD = "put"
ROUTE_SPEC = {
    "response": {
        200: CorporationDiscordSettings,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Map existing Discord roles for this corporation (CEO and directors)",
}


def put_corporation_discord_roles(
    request, corporation_id: int, payload: DiscordRoleMappingUpdate
):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    if not is_connected(corporation) or corporation.discord_guild is None:
        return 400, ErrorResponse(detail="not_connected")
    try:
        replace_role_mappings(
            corporation.discord_guild,
            payload.mappings,
            set(CORPORATION_STATES),
        )
    except MappingError as error:
        return 400, ErrorResponse(detail=error.code)
    return corporation_discord_settings(corporation)
