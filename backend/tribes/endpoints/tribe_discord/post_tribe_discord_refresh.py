"""POST /{tribe_id}/discord/refresh - re-read the tribe server's roles."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.guild_roles import queue_snapshot, tribe_discord_settings
from tribes.endpoints.tribe_discord.access import (
    can_manage_tribe_discord,
    load_tribe,
)
from tribes.endpoints.tribe_discord.schemas import TribeDiscordSettings

PATH = "/{tribe_id}/discord/refresh"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        200: TribeDiscordSettings,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Re-read this tribe's Discord roles (chiefs)",
}


def post_tribe_discord_refresh(request, tribe_id: int):
    tribe = load_tribe(tribe_id)
    if tribe is None:
        return 404, ErrorResponse(detail="Tribe not found")
    if not can_manage_tribe_discord(request.user, tribe):
        return 403, ErrorResponse(detail="Not authorised")
    if tribe.discord_guild_id is None:
        return 400, ErrorResponse(detail="not_connected")
    queue_snapshot(tribe.discord_guild_id)
    return tribe_discord_settings(tribe)
