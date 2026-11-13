"""POST "/requests/{request_id}/discord-pass" - pass on a request from its DM (Discord bot)."""

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

PATH = "/requests/{request_id}/discord-pass"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Pass on a request from its DM (Discord bot).",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_discord_pass(request, request_id: int, payload: DiscordActionBody):
    user = discord_user(request, payload.discord_user_id)
    req = get_request(request_id)
    new = service.pass_request(req, user)
    if new is None:
        return ok("Passed. No other mentor fits, so the pilot was told.")
    return ok("Passed. The next mentor who fits has it.")
