"""POST "/classes" - set up a class (learning managers, from Settings)."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    handles_errors,
    require_manage,
)
from learning.mentors import requirements as reqs
from learning.mentors import service
from learning.mentors.schemas import (
    MentorClassBody,
    MentorClassCreatedResponse,
)
from learning.mentors.service import MentorError
from learning.models import MENTOR_CLASS_COVER_CHOICES, MentorClass

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
    cover = (payload.cover_image_url or "").strip()
    if cover not in dict(MENTOR_CLASS_COVER_CHOICES):
        raise MentorError("Pick a background from the gallery.")
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
    mc.cover_image_url = cover


@handles_errors
def post_class(request, payload: MentorClassBody):
    require_manage(request.user)
    mc = MentorClass(author=request.user)
    apply_body(mc, payload)
    mc.slug = service.unique_slug(mc.title)
    mc.save()
    return 201, {"id": mc.pk, "slug": mc.slug}
