"""DELETE "/{tribe_id}/groups/{group_id}/invitations/{invitation_id}" - withdraw."""

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.invitations.schemas import InvitationSchema
from tribes.endpoints.invitations.serializers import serialize_invitation
from tribes.helpers import user_can_manage_group
from tribes.helpers.invitations import InvitationError, withdraw_invitation
from tribes.models import TribeGroup, TribeGroupInvitation

PATH = "/{tribe_id}/groups/{group_id}/invitations/{invitation_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Withdraw a waiting invite (people who manage the group).",
    "response": {200: InvitationSchema, 400: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Invitations"])


def delete_group_invitation(
    request, tribe_id: int, group_id: int, invitation_id: int
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {
            "detail": "Only people who manage this group can withdraw invites."
        }
    invitation = (
        TribeGroupInvitation.objects.select_related("tribe_group__tribe")
        .filter(pk=invitation_id, tribe_group=tg)
        .first()
    )
    if not invitation:
        return 404, {"detail": "Invite not found."}
    try:
        withdraw_invitation(invitation)
    except InvitationError as exc:
        return exc.status_code, {"detail": str(exc)}
    return 200, serialize_invitation(invitation)


router.delete(PATH, **ROUTE_SPEC)(delete_group_invitation)
