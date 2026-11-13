"""POST "/requests/{request_id}/accept" - accept a request and book its time (mentor)."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    get_request,
    handles_errors,
    ok,
)
from learning.mentors import service
from learning.mentors.schemas import (
    MentorActionResponse,
    AcceptMentorRequestBody,
)

PATH = "/requests/{request_id}/accept"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Accept a request and book its time (mentor).",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_request_accept(
    request, request_id: int, payload: AcceptMentorRequestBody
):
    service.accept(
        get_request(request_id), request.user, payload.starts_at, payload.bring
    )
    return ok("Booked. You each have a DM with the time and the other's name.")
