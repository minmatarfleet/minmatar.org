"""POST "/requests/{request_id}/cancel" - cancel a class (pilot or mentor)."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    get_request,
    handles_errors,
    ok,
)
from learning.mentors import service
from learning.mentors.schemas import MentorActionResponse

PATH = "/requests/{request_id}/cancel"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Cancel a class (pilot or mentor).",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_request_cancel(request, request_id: int):
    service.cancel(get_request(request_id), request.user)
    return ok("Cancelled. The other pilot has been told.")
