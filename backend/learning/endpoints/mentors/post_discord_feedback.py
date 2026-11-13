"""POST "/requests/{request_id}/discord-feedback" - answer how a class went from its DM (Discord bot)."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    discord_user,
    get_request,
    handles_errors,
    ok,
)
from learning.mentors import service
from learning.mentors.schemas import DiscordFeedbackBody, MentorActionResponse

PATH = "/requests/{request_id}/discord-feedback"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Answer how a class went from its DM (Discord bot).",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_discord_feedback(
    request, request_id: int, payload: DiscordFeedbackBody
):
    user = discord_user(request, payload.discord_user_id)
    req = get_request(request_id)
    service.feedback(req, user, payload.answer, payload.note)
    return ok("Thanks. That goes to alliance leadership only.")
