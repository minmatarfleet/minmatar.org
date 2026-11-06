"""POST "/chief-volunteers/{volunteer_id}/discord-appoint".

Appoint a volunteer from the executor's Discord DM (bot).
"""

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.chief_volunteers.schemas import DiscordChiefActionRequest
from tribes.endpoints.chief_volunteers._answer import (
    NOT_EXECUTOR,
    discord_actor,
    RESPONSES,
    answer,
)
from tribes.helpers.chiefs import appoint

PATH = "/chief-volunteers/{volunteer_id}/discord-appoint"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Appoint a volunteer from the executor's Discord DM (bot).",
    "response": RESPONSES,
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Chiefs"])


def post_chief_volunteer_discord_appoint(
    request, volunteer_id: int, payload: DiscordChiefActionRequest
):
    actor = discord_actor(request, payload)
    if actor is None:
        return 403, NOT_EXECUTOR
    return answer(appoint, volunteer_id, actor)


router.post(PATH, **ROUTE_SPEC)(post_chief_volunteer_discord_appoint)
