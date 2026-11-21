"""POST "/requests/{request_id}/reschedule" - change a booked class's time."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    get_request,
    handles_errors,
    ok,
)
from learning.mentors import service
from learning.mentors.schemas import (
    AcceptMentorRequestBody,
    MentorActionResponse,
)

PATH = "/requests/{request_id}/reschedule"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Change the time of a booked class (mentor).",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_request_reschedule(
    request, request_id: int, payload: AcceptMentorRequestBody
):
    changed = service.reschedule(
        get_request(request_id),
        request.user,
        payload.starts_at,
        payload.bring,
    )
    if not changed:
        return ok("That's already the time.")
    return ok("Saved. You each have a DM with the new time.")
