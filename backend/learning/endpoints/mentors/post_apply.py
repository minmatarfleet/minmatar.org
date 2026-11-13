"""POST "/apply" - ask to become a mentor."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    handles_errors,
    ok,
    require_request_access,
)
from learning.mentors import service
from learning.mentors.schemas import MentorActionResponse, MentorApplyBody
from learning.mentors.service import MentorError
from learning.models import MentorProfile

PATH = "/apply"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Ask learning managers to make you a mentor.",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_apply(request, payload: MentorApplyBody):
    require_request_access(request.user)
    profile = service.profile_for(request.user)
    if profile and profile.status in (
        MentorProfile.STATUS_APPLIED,
        MentorProfile.STATUS_APPROVED,
    ):
        raise MentorError("You've already asked.")
    if profile is None:
        profile = MentorProfile(user=request.user)
        service.seed_mentor_availability(profile)
    profile.status = MentorProfile.STATUS_APPLIED
    profile.application_note = (payload.note or "").strip()[:1000]
    profile.save()
    return ok("Sent. A learning manager will look at it.")
