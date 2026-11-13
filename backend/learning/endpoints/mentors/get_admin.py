"""GET "/admin" - Settings for learning managers."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    handles_errors,
    require_manage,
)
from learning.mentors import views
from learning.mentors.schemas import MentorsAdminResponse

PATH = "/admin"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Class reports, classes to review, and mentors.",
    "auth": AuthBearer(),
    "response": {200: MentorsAdminResponse, **ERRORS},
}


@handles_errors
def get_admin(request):
    require_manage(request.user)
    return 200, views.admin()
