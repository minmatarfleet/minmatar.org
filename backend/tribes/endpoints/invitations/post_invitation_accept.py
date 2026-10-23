"""POST "/invitations/{invitation_id}/accept" - join by invite."""

from ninja import Router

from authentication import AuthBearer
from discord.exceptions import DiscordRoleAssignmentError
from tribes.endpoints.invitations.schemas import AcceptInvitationRequest
from tribes.endpoints.memberships.schemas import MembershipSchema
from tribes.endpoints.memberships.serializers import serialize_membership
from tribes.helpers.invitations import InvitationError, accept_invitation
from tribes.models import TribeGroupInvitation

PATH = "/invitations/{invitation_id}/accept"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Accept a tribe group invite: join at once with the picked characters.",
    "response": {
        200: MembershipSchema,
        400: dict,
        403: dict,
        404: dict,
        502: dict,
    },
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Invitations"])


def post_invitation_accept(
    request, invitation_id: int, payload: AcceptInvitationRequest
):
    invitation = (
        TribeGroupInvitation.objects.select_related(
            "tribe_group__tribe", "invited_by"
        )
        .filter(pk=invitation_id)
        .first()
    )
    if not invitation or invitation.user_id != request.user.pk:
        return 404, {"detail": "Invite not found."}
    try:
        membership = accept_invitation(
            invitation, request.user, payload.character_ids
        )
    except InvitationError as exc:
        return exc.status_code, {"detail": str(exc)}
    except DiscordRoleAssignmentError:
        # The role sync rolls the join back, so the invite is still waiting.
        return 502, {
            "detail": "Discord didn't give you the group role, so you "
            "haven't joined yet. Try again in a minute."
        }
    return 200, serialize_membership(membership, include_characters=True)


router.post(PATH, **ROUTE_SPEC)(post_invitation_accept)
