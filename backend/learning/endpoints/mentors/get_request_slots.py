"""GET "/requests/{request_id}/slots" - times both pilots play."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    get_request,
    handles_errors,
)
from learning.mentors import service, views
from learning.mentors.schemas import MentorSlotsResponse
from learning.mentors.service import MentorError

PATH = "/requests/{request_id}/slots"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Suggested times inside both pilots' timezones and days.",
    "auth": AuthBearer(),
    "response": {200: MentorSlotsResponse, **ERRORS},
}


@handles_errors
def get_request_slots(request, request_id: int):
    req = get_request(request_id)
    if req.mentor.user_id != request.user.pk:
        raise MentorError("This request isn't yours.", 403)
    return 200, {
        "request": views.request_rows([req], request.user)[0],
        "mentor_availability": views.availability(
            service.mentor_availability(req.mentor)
        ),
        "slots": service.slots(req),
    }
