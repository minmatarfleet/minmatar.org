"""GET "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/history"."""

from typing import List, Optional

from pydantic import BaseModel
from ninja import Router

from authentication import AuthBearer
from tribes.helpers import user_can_manage_group
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipHistory,
)

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/history"
ROUTE_SPEC = {
    "summary": "Status history for a tribe group membership (chief or own).",
    "response": {200: List["MembershipHistorySchema"], 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Memberships"])


class MembershipHistorySchema(BaseModel):
    id: int
    membership_id: int
    from_status: str
    to_status: str
    changed_at: str
    changed_by_id: Optional[int] = None
    reason: str


def get_membership_history(
    request, tribe_id: int, group_id: int, membership_id: int
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    membership = TribeGroupMembership.objects.filter(
        pk=membership_id, tribe_group=tg
    ).first()
    if not membership:
        return 404, {"detail": "Membership not found."}

    is_own = membership.user_id == request.user.pk
    if not is_own and not user_can_manage_group(request.user, tg):
        return 403, {"detail": "Access denied."}

    rows = TribeGroupMembershipHistory.objects.filter(
        membership=membership
    ).order_by("changed_at")

    return 200, [
        MembershipHistorySchema(
            id=h.pk,
            membership_id=h.membership_id,
            from_status=h.from_status,
            to_status=h.to_status,
            changed_at=h.changed_at.isoformat(),
            changed_by_id=h.changed_by_id,
            reason=h.reason,
        )
        for h in rows
    ]


router.get(PATH, **ROUTE_SPEC)(get_membership_history)
