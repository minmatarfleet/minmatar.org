"""POST "/classes/{class_id}/submit" - send a class for review."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    get_class,
    handles_errors,
    ok,
)
from learning.mentors import service
from learning.mentors.schemas import MentorActionResponse
from learning.mentors.service import MentorError
from learning.models import MentorClass

PATH = "/classes/{class_id}/submit"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Send a class to learning managers for review.",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_class_submit(request, class_id: int):
    mc = get_class(class_id)
    if mc.author_id != request.user.pk:
        raise MentorError("Only the author can send this class.", 403)
    if mc.status not in (MentorClass.STATUS_DRAFT, MentorClass.STATUS_HIDDEN):
        raise MentorError("This class is already sent.")
    service.set_class_status(mc, MentorClass.STATUS_REVIEW)
    return ok("Sent for review.")
