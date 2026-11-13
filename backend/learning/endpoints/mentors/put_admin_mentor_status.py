"""PUT "/admin/mentors/{mentor_id}/status" - approve, decline or remove."""

from django.utils import timezone

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    handles_errors,
    ok,
    require_manage,
)
from learning.mentors.schemas import MentorActionResponse, MentorStatusBody
from learning.mentors.service import MentorError
from learning.models import MentorProfile

PATH = "/admin/mentors/{mentor_id}/status"
METHOD = "put"
ROUTE_SPEC = {
    "summary": "Approve, decline or remove a mentor.",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def put_admin_mentor_status(
    request, mentor_id: int, payload: MentorStatusBody
):
    require_manage(request.user)
    profile = MentorProfile.objects.filter(pk=mentor_id).first()
    if profile is None:
        raise MentorError("Mentor not found.", 404)
    if payload.status not in dict(MentorProfile.STATUS_CHOICES):
        raise MentorError("Unknown status.")
    profile.status = payload.status
    profile.decided_by = request.user
    profile.decided_at = timezone.now()
    profile.save()
    return ok(f"Mentor {profile.get_status_display().lower()}.")
