"""POST "/classes/{class_id}/teachers" - invite a mentor to teach a class."""

from authentication import AuthBearer
from eveonline.models import EvePlayer
from learning.endpoints.mentors.common import (
    ERRORS,
    get_class,
    handles_errors,
    ok,
)
from learning.mentors import views
from learning.mentors.schemas import InviteTeacherBody, MentorActionResponse
from learning.mentors.service import MentorError
from learning.models import MentorClassTeacher, MentorProfile

PATH = "/classes/{class_id}/teachers"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Invite another mentor to teach this class.",
    "auth": AuthBearer(),
    "response": {200: MentorActionResponse, **ERRORS},
}


@handles_errors
def post_class_teachers(request, class_id: int, payload: InviteTeacherBody):

    mc = get_class(class_id)
    if not views.can_edit_class(request.user, mc):
        raise MentorError("Only the author can invite mentors.", 403)
    name = (payload.character_name or "").strip()
    player = (
        EvePlayer.objects.filter(
            primary_character__character_name__iexact=name
        )
        .select_related("user")
        .first()
    )
    if player is None:
        raise MentorError(f"No pilot with the main character {name}.", 404)
    profile = MentorProfile.objects.filter(
        user=player.user, status=MentorProfile.STATUS_APPROVED
    ).first()
    if profile is None:
        raise MentorError(f"{name} isn't a mentor.")
    _, created = MentorClassTeacher.objects.get_or_create(
        mentor_class=mc,
        mentor=profile,
        defaults={"status": MentorClassTeacher.STATUS_INVITED},
    )
    if not created:
        raise MentorError(f"{name} already teaches or is invited.")
    return ok(f"Invited {name}. They'll see it in My settings.")
