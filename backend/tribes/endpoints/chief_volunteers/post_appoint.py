"""POST "/chief-volunteers/{volunteer_id}/appoint".

Appoint a volunteer as chief (executor only).
"""

from ninja import Router

from authentication import AuthBearer

from tribes.endpoints.chief_volunteers._answer import (
    RESPONSES,
    answer,
)
from tribes.helpers.chiefs import appoint

PATH = "/chief-volunteers/{volunteer_id}/appoint"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Appoint a volunteer as chief (executor only).",
    "response": RESPONSES,
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Chiefs"])


def post_chief_volunteer_appoint(request, volunteer_id: int):
    return answer(appoint, volunteer_id, request.user)


router.post(PATH, **ROUTE_SPEC)(post_chief_volunteer_appoint)
