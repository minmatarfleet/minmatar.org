"""GET "/classes/{class_id}/edit" - a class in the editor."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import ERRORS, get_class, handles_errors
from learning.mentors import views
from learning.mentors.schemas import MentorClassEditResponse
from learning.mentors.service import MentorError

PATH = "/classes/{class_id}/edit"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "A class for a learning manager to edit.",
    "auth": AuthBearer(),
    "response": {200: MentorClassEditResponse, **ERRORS},
}


@handles_errors
def get_class_edit(request, class_id: int):
    mc = get_class(class_id)
    if not views.can_edit_class(request.user, mc):
        raise MentorError("Learning managers only.", 403)
    return 200, views.class_edit(request.user, mc)
