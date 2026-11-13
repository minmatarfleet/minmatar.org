"""GET "/settings" - My settings: availability and classes taught."""

from authentication import AuthBearer
from learning.mentors import views
from learning.mentors.schemas import MentorSettingsResponse

PATH = "/settings"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "The mentor's times, capacity and classes.",
    "auth": AuthBearer(),
    "response": {200: MentorSettingsResponse},
}


def get_settings(request):
    return views.settings(request.user)
