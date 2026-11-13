"""POST "/admin/mentors" - make a pilot a mentor directly."""

from django.utils import timezone

from authentication import AuthBearer
from eveonline.models import EvePlayer
from learning.endpoints.mentors.common import (
    ERRORS,
    handles_errors,
    ok,
    require_manage,
)
from learning.mentors import service
from learning.mentors.schemas import InviteTeacherBody, MentorActionResponse
from learning.mentors.service import MentorError
from learning.models import MentorProfile

PATH = "/admin/mentors"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Make a pilot a mentor by their main character's name.",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_admin_mentor(request, payload: InviteTeacherBody):

    require_manage(request.user)
    name = (payload.character_name or "").strip()
    player = (
        EvePlayer.objects.filter(
            primary_character__character_name__iexact=name
        )
        .select_related("user")
        .first()
    )
    if player is None or player.user is None:
        raise MentorError(f"No pilot with the main character {name}.", 404)
    profile = MentorProfile.objects.filter(user=player.user).first()
    if profile is None:
        profile = MentorProfile(user=player.user)
        service.seed_mentor_availability(profile)
    profile.status = MentorProfile.STATUS_APPROVED
    profile.decided_by = request.user
    profile.decided_at = timezone.now()
    profile.save()
    return ok(f"{name} is a mentor.")
