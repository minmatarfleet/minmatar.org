"""POST "/requests/{request_id}/discord-confirm" - confirm attendance from the reminder DM (Discord bot)."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    discord_user,
    get_request,
    handles_errors,
    ok,
)
from learning.mentors import service
from learning.mentors.schemas import DiscordActionBody, MentorActionResponse

PATH = "/requests/{request_id}/discord-confirm"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Confirm attendance from the reminder DM (Discord bot).",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_discord_confirm(request, request_id: int, payload: DiscordActionBody):
    user = discord_user(request, payload.discord_user_id)
    req = get_request(request_id)
    service.confirm(req, user)
    return ok("See you there.")
