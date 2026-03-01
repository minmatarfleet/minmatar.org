"""POST "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/characters"."""

from authentication import AuthBearer
from tribes.endpoints.memberships.schemas import (
    AddCharacterRequest,
    MembershipCharacterSchema,
)
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
)
from eveonline.models import EveCharacter

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/characters"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Commit a character to a membership.",
    "response": {
        200: MembershipCharacterSchema,
        400: dict,
        403: dict,
        404: dict,
    },
    "auth": AuthBearer(),
}


def post_membership_character(
    request,
    tribe_id: int,
    group_id: int,
    membership_id: int,
    payload: AddCharacterRequest,
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    membership = TribeGroupMembership.objects.filter(
        pk=membership_id, tribe_group=tg, user=request.user
    ).first()
    if not membership:
        return 404, {"detail": "Membership not found."}
    if membership.status not in [
        TribeGroupMembership.STATUS_PENDING,
        TribeGroupMembership.STATUS_APPROVED,
    ]:
        return 400, {"detail": "Cannot add characters to a closed membership."}

    character = EveCharacter.objects.filter(
        character_id=payload.character_id, user=request.user
    ).first()
    if not character:
        return 404, {
            "detail": "Character not found or does not belong to you."
        }

    if TribeGroupMembershipCharacter.objects.filter(
        membership=membership, character=character, left_at__isnull=True
    ).exists():
        return 400, {
            "detail": "Character already committed to this membership."
        }

    mc = TribeGroupMembershipCharacter.objects.create(
        membership=membership, character=character
    )
    return 200, MembershipCharacterSchema(
        id=mc.pk,
        character_id=character.character_id,
        character_name=character.character_name,
        committed_at=mc.committed_at.isoformat(),
        left_at=None,
    )
