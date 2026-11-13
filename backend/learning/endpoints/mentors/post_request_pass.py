"""POST "/requests/{request_id}/pass" - pass on a request (mentor)."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    get_request,
    handles_errors,
    ok,
)
from learning.mentors import service
from learning.mentors.schemas import MentorActionResponse

PATH = "/requests/{request_id}/pass"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Pass on a request (mentor).",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_request_pass(request, request_id: int):
    new = service.pass_request(get_request(request_id), request.user)
    if new is None:
        return ok("Passed. No other mentor fits, so the pilot was told.")
    return ok("Passed. The next mentor who fits has it.")
