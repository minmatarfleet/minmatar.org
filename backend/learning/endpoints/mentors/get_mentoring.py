"""GET "/mentoring" - My mentees: requests, booked classes, record."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import ERRORS, handles_errors
from learning.mentors import service, views
from learning.mentors.schemas import MentoringResponse
from learning.mentors.service import MentorError

PATH = "/mentoring"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "The mentor's requests and booked classes.",
    "auth": AuthBearer(),
    "response": {200: MentoringResponse, **ERRORS},
}


@handles_errors
def get_mentoring(request):
    profile = service.approved_profile(request.user)
    if profile is None:
        raise MentorError("You aren't a mentor.", 403)
    return 200, views.mentoring(profile)
