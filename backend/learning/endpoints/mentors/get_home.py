"""GET "" - Find a mentor: the viewer's classes and the mentors who fit.

Logged-out visitors get the mentors read-only (see views.guest_home)."""

from authentication import AuthLenient
from learning.mentors import views
from learning.mentors.schemas import MentorsHomeResponse

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Find a mentor: your classes and mentors sorted by fit.",
    "auth": AuthLenient(),
    "response": {200: MentorsHomeResponse},
}


def get_home(request):
    return views.home(request.user)
