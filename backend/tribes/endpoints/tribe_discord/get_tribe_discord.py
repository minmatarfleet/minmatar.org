"""GET /{tribe_id}/discord - the tribe's own Discord server."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.guild_roles import tribe_discord_settings
from tribes.endpoints.tribe_discord.access import (
    can_manage_tribe_discord,
    load_tribe,
)
from tribes.endpoints.tribe_discord.schemas import TribeDiscordSettings

PATH = "/{tribe_id}/discord"
METHOD = "get"
ROUTE_SPEC = {
    "response": {
        200: TribeDiscordSettings,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "The tribe's Discord server (chiefs)",
}


def get_tribe_discord(request, tribe_id: int):
    tribe = load_tribe(tribe_id)
    if tribe is None:
        return 404, ErrorResponse(detail="Tribe not found")
    if not can_manage_tribe_discord(request.user, tribe):
        return 403, ErrorResponse(detail="Not authorised")
    return tribe_discord_settings(tribe)
