"""POST "/classes/{class_id}/teach" - teach a class (accept or join)."""

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
from learning.models import MentorClass, MentorClassTeacher

PATH = "/classes/{class_id}/teach"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Start teaching a class: accept an invite or join it.",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_class_teach(request, class_id: int):
    profile = service.approved_profile(request.user)
    if profile is None:
        raise MentorError("You aren't a mentor.", 403)
    mc = get_class(class_id)
    # Mentors join published classes; an invite also lets them join a draft.
    invited = MentorClassTeacher.objects.filter(
        mentor_class=mc, mentor=profile
    ).exists()
    if mc.status != MentorClass.STATUS_PUBLISHED and not invited:
        raise MentorError("That class isn't published.")
    row, _ = MentorClassTeacher.objects.get_or_create(
        mentor_class=mc, mentor=profile
    )
    row.status = MentorClassTeacher.STATUS_ACCEPTED
    row.save(update_fields=["status"])
    return ok(f"You teach {mc.title} now.")
