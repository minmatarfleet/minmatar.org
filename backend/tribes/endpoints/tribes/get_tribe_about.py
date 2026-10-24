"""GET "/{tribe_id}/about" - a year of the tribe, names for alliance members."""

import copy

from ninja import Router

from authentication import AuthOptional
from tribes.endpoints.tribes.schemas import TribeAboutSchema
from tribes.helpers import user_can_view_group_roster
from tribes.helpers.about import tribe_about
from tribes.models import Tribe, TribeGroup

PATH = "/{tribe_id}/about"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Tribe About page: totals and records; named pilots for roster viewers.",
    "response": {200: TribeAboutSchema, 404: dict},
    "auth": AuthOptional(),
}

router = Router(tags=["Tribes"])


def get_tribe_about(request, tribe_id: int):
    tribe = Tribe.objects.filter(pk=tribe_id).first()
    if not tribe:
        return 404, {"detail": "Tribe not found."}

    cached = tribe_about(tribe.pk)
    if cached is None:
        return 200, TribeAboutSchema(tribe_id=tribe.pk, slug=tribe.slug)

    about = copy.deepcopy(cached)
    groups = {
        g.pk: g for g in TribeGroup.objects.filter(tribe=tribe, is_active=True)
    }
    visible = {
        pk
        for pk, group in groups.items()
        if user_can_view_group_roster(request.user, group)
    }
    for group in about.get("groups") or []:
        if group["id"] not in visible:
            group["top_pilots"] = []

    return 200, TribeAboutSchema(ready=True, **about)


router.get(PATH, **ROUTE_SPEC)(get_tribe_about)
