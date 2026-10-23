"""POST "/invitations/{invitation_id}/discord-decline" - the DM's Decline."""

from ninja import Router

from authentication import AuthBearer, is_service_account
from discord.models import DiscordUser
from tribes.endpoints.invitations.schemas import (
    DiscordDeclineRequest,
    InvitationSchema,
)
from tribes.endpoints.invitations.serializers import serialize_invitation
from tribes.helpers.invitations import InvitationError, decline_invitation
from tribes.models import TribeGroupInvitation

PATH = "/invitations/{invitation_id}/discord-decline"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Decline a tribe group invite from its Discord DM (bot).",
    "response": {200: InvitationSchema, 400: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Invitations"])


def post_invitation_discord_decline(
    request, invitation_id: int, payload: DiscordDeclineRequest
):
    invitation = (
        TribeGroupInvitation.objects.select_related("tribe_group__tribe")
        .filter(pk=invitation_id)
        .first()
    )
    if not invitation:
        return 404, {"detail": "Invite not found."}
    discord_user = DiscordUser.objects.filter(
        id=payload.discord_user_id
    ).first()
    if not discord_user or discord_user.user_id != invitation.user_id:
        return 403, {"detail": "This invite isn't yours."}
    requester = request.user
    if requester.pk != invitation.user_id and not is_service_account(
        requester
    ):
        return 403, {"detail": "This invite isn't yours."}
    try:
        decline_invitation(invitation, discord_user.user)
    except InvitationError as exc:
        return exc.status_code, {"detail": str(exc)}
    return 200, serialize_invitation(invitation)


router.post(PATH, **ROUTE_SPEC)(post_invitation_discord_decline)
