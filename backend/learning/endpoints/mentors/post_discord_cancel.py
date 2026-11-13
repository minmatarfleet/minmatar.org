"""POST "/requests/{request_id}/discord-cancel" - cancel a class from its DM (Discord bot)."""

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

PATH = "/requests/{request_id}/discord-cancel"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Cancel a class from its DM (Discord bot).",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_discord_cancel(request, request_id: int, payload: DiscordActionBody):
    user = discord_user(request, payload.discord_user_id)
    req = get_request(request_id)
    service.cancel(req, user)
    return ok("Cancelled. The other pilot has been told.")
