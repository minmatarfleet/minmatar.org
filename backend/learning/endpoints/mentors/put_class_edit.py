"""PUT "/classes/{class_id}/edit" - save a class."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import ERRORS, get_class, handles_errors
from learning.endpoints.mentors.post_class import apply_body
from learning.mentors import service, views
from learning.mentors.schemas import MentorClassBody, MentorClassEditResponse
from learning.mentors.service import MentorError

PATH = "/classes/{class_id}/edit"
METHOD = "put"
ROUTE_SPEC = {
    "summary": "Save a class (learning managers).",
    "auth": AuthBearer(),
    "response": {200: MentorClassEditResponse, **ERRORS},
}


@handles_errors
def put_class_edit(request, class_id: int, payload: MentorClassBody):
    mc = get_class(class_id)
    if not views.can_edit_class(request.user, mc):
        raise MentorError("Learning managers only.", 403)
    apply_body(mc, payload)
    mc.save()
    service.sync_learning(mc)
    return 200, views.class_edit(request.user, mc)
