"""POST "/chief-volunteers/{volunteer_id}/decline".

Not now: leave the seat open (executor only).
"""

from ninja import Router

from authentication import AuthBearer

from tribes.endpoints.chief_volunteers._answer import (
    RESPONSES,
    answer,
)
from tribes.helpers.chiefs import decline

PATH = "/chief-volunteers/{volunteer_id}/decline"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Not now: leave the seat open (executor only).",
    "response": RESPONSES,
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Chiefs"])


def post_chief_volunteer_decline(request, volunteer_id: int):
    return answer(decline, volunteer_id, request.user)


router.post(PATH, **ROUTE_SPEC)(post_chief_volunteer_decline)
