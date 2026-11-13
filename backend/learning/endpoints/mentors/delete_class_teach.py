"""DELETE "/classes/{class_id}/teach" - stop teaching a class."""

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
from learning.models import MentorClassTeacher

PATH = "/classes/{class_id}/teach"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Stop teaching a class (or decline the invite).",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def delete_class_teach(request, class_id: int):
    profile = service.profile_for(request.user)
    if profile is None:
        raise MentorError("You aren't a mentor.", 403)
    deleted, _ = MentorClassTeacher.objects.filter(
        mentor_class=get_class(class_id), mentor=profile
    ).delete()
    if not deleted:
        raise MentorError("You don't teach this class.")
    return ok("Done. Requests already asked or booked stay with you.")
