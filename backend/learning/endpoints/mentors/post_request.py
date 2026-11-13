"""POST "/requests" - ask a mentor for a class."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    get_class,
    handles_errors,
    require_request_access,
)
from learning.mentors import service, views
from learning.mentors.schemas import (
    CreateMentorRequestBody,
    MentorRequestSchema,
)
from learning.mentors.service import MentorError
from learning.models import MentorProfile

PATH = "/requests"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Request a class from a mentor.",
    "auth": AuthBearer(),
    "response": {201: MentorRequestSchema, **ERRORS},
}


@handles_errors
def post_request(request, payload: CreateMentorRequestBody):
    require_request_access(request.user)
    mentor = MentorProfile.objects.filter(pk=payload.mentor_id).first()
    if mentor is None:
        raise MentorError("Mentor not found.", 404)
    req = service.create_request(
        request.user,
        mentor,
        get_class(payload.class_id),
        note=payload.note,
        weekday_brackets=payload.weekday_brackets,
        weekend_brackets=payload.weekend_brackets,
        days=payload.days,
    )
    return 201, views.request_rows([req], request.user)[0]
