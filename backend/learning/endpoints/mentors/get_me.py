"""GET "/me" - what the viewer can do with mentors (for the tabs)."""

from authentication import AuthBearer
from learning.mentors import views
from learning.mentors.schemas import MentorsMeResponse

PATH = "/me"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Mentor roles of the authenticated user.",
    "auth": AuthBearer(),
    "response": {200: MentorsMeResponse},
}


def get_me(request):
    return views.me(request.user)
