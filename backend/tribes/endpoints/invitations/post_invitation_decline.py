"""POST "/invitations/{invitation_id}/decline" - say no from the site."""

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.invitations.schemas import InvitationSchema
from tribes.endpoints.invitations.serializers import serialize_invitation
from tribes.helpers.invitations import InvitationError, decline_invitation
from tribes.models import TribeGroupInvitation

PATH = "/invitations/{invitation_id}/decline"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Decline a tribe group invite.",
    "response": {200: InvitationSchema, 400: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Invitations"])


def post_invitation_decline(request, invitation_id: int):
    invitation = (
        TribeGroupInvitation.objects.select_related("tribe_group__tribe")
        .filter(pk=invitation_id)
        .first()
    )
    if not invitation or invitation.user_id != request.user.pk:
        return 404, {"detail": "Invite not found."}
    try:
        decline_invitation(invitation, request.user)
    except InvitationError as exc:
        return exc.status_code, {"detail": str(exc)}
    return 200, serialize_invitation(invitation)


router.post(PATH, **ROUTE_SPEC)(post_invitation_decline)
