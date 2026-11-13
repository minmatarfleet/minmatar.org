"""GET "/admin/class-options" - what the class editor offers."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    handles_errors,
    require_manage,
)
from learning.mentors import views
from learning.mentors.schemas import MentorClassOptionsResponse

PATH = "/admin/class-options"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "The cover gallery and requirement kinds for the class editor.",
    "auth": AuthBearer(),
    "response": {200: MentorClassOptionsResponse, **ERRORS},
}


@handles_errors
def get_class_options(request):
    require_manage(request.user)
    return 200, views.class_options()
