"""DELETE /{tribe_id}/discord - disconnect the tribe's Discord server."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.guild_roles import tribe_discord_settings, unlink_tribe_guild
from eveonline.tasks.corporations import release_corporation_discord_guild
from tribes.endpoints.tribe_discord.access import (
    can_manage_tribe_discord,
    load_tribe,
)
from tribes.endpoints.tribe_discord.schemas import TribeDiscordSettings

PATH = "/{tribe_id}/discord"
METHOD = "delete"
ROUTE_SPEC = {
    "response": {
        200: TribeDiscordSettings,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Disconnect the tribe's Discord server (chiefs)",
}


def delete_tribe_discord(request, tribe_id: int):
    tribe = load_tribe(tribe_id)
    if tribe is None:
        return 404, ErrorResponse(detail="Tribe not found")
    if not can_manage_tribe_discord(request.user, tribe):
        return 403, ErrorResponse(detail="Not authorised")
    guild_id = unlink_tribe_guild(tribe)
    if guild_id is not None:
        release_corporation_discord_guild.delay(guild_id, "")
    return tribe_discord_settings(tribe)
