"""GET "/classes/{slug}" - a class, checked against the viewer."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import ERRORS, handles_errors
from learning.mentors import views
from learning.mentors.schemas import MentorClassDetailResponse
from learning.mentors.service import MentorError
from learning.models import MentorClass

PATH = "/classes/{slug}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "A class, its requirements for you, and its mentors.",
    "auth": AuthBearer(),
    "response": {200: MentorClassDetailResponse, **ERRORS},
}


@handles_errors
def get_class(request, slug: str):
    mc = MentorClass.objects.filter(slug=slug).first()
    if mc is None:
        raise MentorError("Class not found.", 404)
    if mc.status != MentorClass.STATUS_PUBLISHED and not views.can_edit_class(
        request.user, mc
    ):
        raise MentorError("Class not found.", 404)
    return 200, views.class_detail(request.user, mc)
