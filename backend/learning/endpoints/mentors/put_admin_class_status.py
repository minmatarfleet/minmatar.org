"""PUT "/admin/classes/{class_id}/status" - publish, send back or hide."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    get_class,
    handles_errors,
    ok,
    require_manage,
)
from learning.mentors import service
from learning.mentors.schemas import (
    MentorActionResponse,
    MentorClassStatusBody,
)

PATH = "/admin/classes/{class_id}/status"
METHOD = "put"
ROUTE_SPEC = {
    "summary": "Publish a class, send it back to its author, or hide it.",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def put_admin_class_status(
    request, class_id: int, payload: MentorClassStatusBody
):
    require_manage(request.user)
    mc = get_class(class_id)
    service.set_class_status(mc, payload.status, payload.note)
    return ok(f"{mc.title}: {mc.get_status_display().lower()}.")
