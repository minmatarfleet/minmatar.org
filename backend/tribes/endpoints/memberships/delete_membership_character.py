"""DELETE "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/characters/{character_id}"."""

from django.utils import timezone
from ninja import Router

from authentication import AuthBearer
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
)

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/characters/{character_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Remove a character commitment from a membership.",
    "response": {200: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Memberships"])


def delete_membership_character(
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
        pk=membership_id, tribe_group=tg, user=request.user
    ).first()
    if not membership:
        return 404, {"detail": "Membership not found."}

    mc = TribeGroupMembershipCharacter.objects.filter(
        membership=membership,
        character__character_id=character_id,
    ).first()
    if not mc:
        return 404, {"detail": "Character commitment not found."}

    TribeGroupMembershipCharacterHistory.objects.create(
        membership=membership,
        character=mc.character,
        action=TribeGroupMembershipCharacterHistory.ACTION_REMOVED,
        at=timezone.now(),
        by=request.user,
        leave_reason=TribeGroupMembershipCharacterHistory.LEAVE_REASON_VOLUNTARY,
    )
    mc.delete()
    return 200, {"detail": "Character removed from membership."}


router.delete(PATH, **ROUTE_SPEC)(delete_membership_character)
