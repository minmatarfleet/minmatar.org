"""PUT /{tribe_id}/discord - map existing roles on the tribe's server."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.guild_roles import (
    TRIBE_STATES,
    MappingError,
    replace_role_mappings,
    tribe_discord_settings,
)
from tribes.endpoints.tribe_discord.access import (
    can_manage_tribe_discord,
    load_tribe,
)
from tribes.endpoints.tribe_discord.schemas import (
    TribeDiscordMappingUpdate,
    TribeDiscordSettings,
)

PATH = "/{tribe_id}/discord"
METHOD = "put"
ROUTE_SPEC = {
    "response": {
        200: TribeDiscordSettings,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Map existing Discord roles for this tribe (chiefs)",
}


def put_tribe_discord_roles(
    request, tribe_id: int, payload: TribeDiscordMappingUpdate
):
    tribe = load_tribe(tribe_id)
    if tribe is None:
        return 404, ErrorResponse(detail="Tribe not found")
    if not can_manage_tribe_discord(request.user, tribe):
        return 403, ErrorResponse(detail="Not authorised")
    if tribe.discord_guild is None:
        return 400, ErrorResponse(detail="not_connected")
    try:
        replace_role_mappings(
            tribe.discord_guild, payload.mappings, set(TRIBE_STATES)
        )
    except MappingError as error:
        return 400, ErrorResponse(detail=error.code)
    return tribe_discord_settings(tribe)
