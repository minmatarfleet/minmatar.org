"""POST "/classes" - start a class (mentors and learning managers)."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import ERRORS, handles_errors
from learning.mentors import requirements as reqs
from learning.mentors import service, views
from learning.mentors.schemas import (
    MentorClassBody,
    MentorClassCreatedResponse,
)
from learning.mentors.service import MentorError
from learning.models import MentorClass, MentorClassTeacher

PATH = "/classes"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Create a class as a draft.",
    "auth": AuthBearer(),
    "response": {201: MentorClassCreatedResponse, **ERRORS},
}


def apply_body(mc: MentorClass, payload: MentorClassBody) -> None:
    title = (payload.title or "").strip()
    if not title:
        raise MentorError("A class needs a title.")
    if payload.where not in dict(MentorClass.WHERE_CHOICES):
        raise MentorError("Pick where the class happens.")
    if not 15 <= payload.minutes <= 180:
        raise MentorError("A class is 15 to 180 minutes.")
    try:
        rows = reqs.clean([r.dict() for r in payload.requirements])
    except reqs.RequirementError as exc:
        raise MentorError(str(exc)) from exc
    mc.title = title[:120]
    mc.summary = (payload.summary or "").strip()[:2000]
    mc.outline = (payload.outline or "").strip()[:4000]
    mc.minutes = payload.minutes
    mc.where = payload.where
    mc.requirements = rows


@handles_errors
def post_class(request, payload: MentorClassBody):
    profile = service.approved_profile(request.user)
    if profile is None and not views.can_manage(request.user):
        raise MentorError("Only mentors can write classes.", 403)
    mc = MentorClass(author=request.user)
    apply_body(mc, payload)
    mc.slug = service.unique_slug(mc.title)
    mc.save()
    if profile is not None:
        MentorClassTeacher.objects.create(mentor_class=mc, mentor=profile)
    return 201, {"id": mc.pk, "slug": mc.slug}
