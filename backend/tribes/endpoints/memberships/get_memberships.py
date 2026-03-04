"""GET "/{tribe_id}/groups/{group_id}/memberships" - list memberships."""

from typing import List, Optional

from authentication import AuthBearer
from tribes.endpoints.memberships.schemas import MembershipSchema
from tribes.endpoints.memberships.serializers import serialize_membership
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupMembership

PATH = "/{tribe_id}/groups/{group_id}/memberships"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List memberships for a tribe group (chiefs/elders see all; members see own).",
    "response": {200: List[MembershipSchema], 403: dict, 404: dict},
    "auth": AuthBearer(),
}


def get_memberships(
    request,
    tribe_id: int,
    group_id: int,
    status: Optional[str] = None,
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    if user_can_manage_group(request.user, tg):
        qs = TribeGroupMembership.objects.filter(tribe_group=tg)
    else:
        qs = TribeGroupMembership.objects.filter(
            tribe_group=tg, user=request.user
        )

    if status:
        qs = qs.filter(status=status)

    qs = qs.select_related("tribe_group__tribe").prefetch_related(
        "characters__character"
    )

    return 200, [serialize_membership(m) for m in qs]
