"""GET /{tribe_id}/groups/{group_id}/about - a year of the group."""

import copy

from ninja import Router

from authentication import AuthOptional
from tribes.endpoints.tribes.schemas import TribeGroupAboutSchema
from tribes.helpers import user_can_view_group_roster
from tribes.helpers.about import group_about
from tribes.models import TribeGroup

PATH = "/{tribe_id}/groups/{group_id}/about"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Group About tab: a year of totals and records; named pilots for roster viewers.",
    "response": {200: TribeGroupAboutSchema, 404: dict},
    "auth": AuthOptional(),
}

router = Router(tags=["Tribes - Groups"])


def get_tribe_group_about(request, tribe_id: int, group_id: int):
    group = TribeGroup.objects.filter(
        pk=group_id, tribe_id=tribe_id, is_active=True
    ).first()
    if not group:
        return 404, {"detail": "Tribe group not found."}

    cached = group_about(group.pk)
    if cached is None:
        return 200, TribeGroupAboutSchema(
            group_id=group.pk, tribe_id=tribe_id, code=group.code or ""
        )

    about = copy.deepcopy(cached)
    if not user_can_view_group_roster(request.user, group):
        if about.get("year"):
            about["year"]["top_pilots"] = []
        # A hidden roster keeps even its corporations to itself.
        if group.roster_hidden:
            about["corporations"] = []

    return 200, TribeGroupAboutSchema(ready=True, **about)


router.get(PATH, **ROUTE_SPEC)(get_tribe_group_about)
