"""GET "/past" - the viewer's closed classes."""

from authentication import AuthBearer
from learning.mentors import views
from learning.mentors.schemas import MentorRequestSchema

PATH = "/past"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Your past classes.",
    "auth": AuthBearer(),
    "response": {200: list[MentorRequestSchema]},
}


def get_past(request):
    return views.past_classes(request.user)
