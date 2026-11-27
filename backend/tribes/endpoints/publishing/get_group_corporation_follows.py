"""GET "/groups/{group_id}/corporation-follows" - corporations that asked
for the group's fleet posts in their own Discord."""

from typing import List

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints.publishing.corporation_follows import (
    serialize_corporation_follows,
)
from tribes.endpoints.publishing.schemas import GroupCorporationFollowSchema
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup

PATH = "/groups/{group_id}/corporation-follows"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Corporations that follow the group's fleet posts.",
    "description": (
        "Managers of the group only. A follow forwards the roundup, the "
        "quiet pre-ping and the start ping once it is approved."
    ),
    "response": {
        200: List[GroupCorporationFollowSchema],
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Publishing"])


def get_group_corporation_follows(request, group_id: int):
    group = TribeGroup.objects.filter(pk=group_id).first()
    if group is None:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, group):
        return 403, {"detail": "Only the group's managers can see this."}
    return 200, serialize_corporation_follows(group)


router.get(PATH, **ROUTE_SPEC)(get_group_corporation_follows)
