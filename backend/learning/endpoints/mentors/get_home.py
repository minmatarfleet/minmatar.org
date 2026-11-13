"""GET "" - Find a mentor: the viewer's classes and the mentors who fit."""

from authentication import AuthBearer
from learning.mentors import views
from learning.mentors.schemas import MentorsHomeResponse

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Find a mentor: your classes and mentors sorted by fit.",
    "auth": AuthBearer(),
    "response": {200: MentorsHomeResponse},
}


def get_home(request):
    return views.home(request.user)
