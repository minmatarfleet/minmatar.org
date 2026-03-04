"""GET "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/characters/{character_id}/history"."""

from typing import List, Optional

from pydantic import BaseModel
from ninja import Router

from authentication import AuthBearer
from tribes.helpers import user_can_manage_group
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacterHistory,
)

PATH = (
    "/{tribe_id}/groups/{group_id}/memberships/{membership_id}"
    "/characters/{character_id}/history"
)
ROUTE_SPEC = {
    "summary": "Character add/remove history for a membership (chiefs/elders or own).",
    "response": {
        200: List["MembershipCharacterHistorySchema"],
        403: dict,
        404: dict,
    },
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Memberships"])


class MembershipCharacterHistorySchema(BaseModel):
    id: int
    membership_id: int
    character_id: int
    character_name: str
    action: str
    at: str
    by_id: Optional[int] = None
    leave_reason: str


def get_membership_character_history(
    request,
    tribe_id: int,
    group_id: int,
    membership_id: int,
    character_id: int,
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

    rows = (
        TribeGroupMembershipCharacterHistory.objects.filter(
            membership=membership,
            character__character_id=character_id,
        )
        .select_related("character")
        .order_by("at")
    )

    return 200, [
        MembershipCharacterHistorySchema(
            id=h.pk,
            membership_id=h.membership_id,
            character_id=h.character.character_id,
            character_name=h.character.character_name,
            action=h.action,
            at=h.at.isoformat(),
            by_id=h.by_id,
            leave_reason=h.leave_reason,
        )
        for h in rows
    ]


router.get(PATH, **ROUTE_SPEC)(get_membership_character_history)
