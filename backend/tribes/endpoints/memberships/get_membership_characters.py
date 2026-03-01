"""GET "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/characters"."""

from typing import List

from authentication import AuthBearer
from tribes.endpoints.memberships.schemas import MembershipCharacterSchema
from tribes.helpers import user_can_manage_group
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
)

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/characters"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List characters committed to a membership.",
    "response": {200: List[MembershipCharacterSchema], 403: dict, 404: dict},
    "auth": AuthBearer(),
}


def get_membership_characters(
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

    chars = TribeGroupMembershipCharacter.objects.filter(
        membership=membership, left_at__isnull=True
    ).select_related("character")
    return 200, [
        MembershipCharacterSchema(
            id=c.pk,
            character_id=c.character.character_id,
            character_name=c.character.character_name,
            committed_at=c.committed_at.isoformat(),
            left_at=c.left_at.isoformat() if c.left_at else None,
        )
        for c in chars
    ]
