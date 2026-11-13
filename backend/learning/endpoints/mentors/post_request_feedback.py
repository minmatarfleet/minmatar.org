"""POST "/requests/{request_id}/feedback" - answer how a class went (pilot or mentor)."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    get_request,
    handles_errors,
    ok,
)
from learning.mentors import service
from learning.mentors.schemas import MentorActionResponse, MentorFeedbackBody

PATH = "/requests/{request_id}/feedback"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Answer how a class went (pilot or mentor).",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_request_feedback(
    request, request_id: int, payload: MentorFeedbackBody
):
    service.feedback(
        get_request(request_id), request.user, payload.answer, payload.note
    )
    return ok("Thanks. That goes to alliance leadership only.")
