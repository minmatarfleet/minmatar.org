"""DELETE /corporations/{corporation_id}/discord/bot - stop using the bot."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import CorporationDiscordSettings
from eveonline.helpers.corporations.discord_bot import (
    corporation_discord_settings,
    unlink_guild,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation
from eveonline.tasks.corporations import release_corporation_discord_guild

PATH = "corporations/{corporation_id}/discord/bot"
METHOD = "delete"
ROUTE_SPEC = {
    "response": {
        200: CorporationDiscordSettings,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Disconnect the bot from the corporation's Discord "
    "(CEO and directors)",
}


def delete_corporation_discord_bot(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    release = unlink_guild(corporation)
    if release is not None:
        # Revoking the invite and leaving the server are Discord calls.
        release_corporation_discord_guild.delay(
            release.guild_id, release.invite_code
        )
    return corporation_discord_settings(corporation)
