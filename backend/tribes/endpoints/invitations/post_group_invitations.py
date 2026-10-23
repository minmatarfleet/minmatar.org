"""POST "/{tribe_id}/groups/{group_id}/invitations" - invite pilots."""

from typing import List

from authentication import AuthBearer
from tribes.endpoints.invitations.schemas import (
    InvitationSchema,
    SendInvitationsRequest,
)
from tribes.endpoints.invitations.serializers import serialize_invitations
from tribes.helpers import user_can_manage_group
from tribes.helpers.invitations import (
    InvitationError,
    send_invitations,
    users_by_ids,
)
from tribes.models import TribeGroup

PATH = "/{tribe_id}/groups/{group_id}/invitations"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Invite pilots to a tribe group (people who manage it).",
    "response": {200: List[InvitationSchema], 400: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}


def post_group_invitations(
    request, tribe_id: int, group_id: int, payload: SendInvitationsRequest
):
    tg = (
        TribeGroup.objects.select_related("tribe")
        .filter(pk=group_id, tribe_id=tribe_id, is_active=True)
        .first()
    )
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {"detail": "Only people who manage this group can invite."}

    users = users_by_ids(payload.user_ids)
    if len(users) != len(set(payload.user_ids)):
        return 400, {"detail": "Some of those pilots don't exist."}
    try:
        invitations = send_invitations(
            tg, users, request.user, note=payload.note
        )
    except InvitationError as exc:
        return exc.status_code, {"detail": str(exc)}
    return 200, serialize_invitations(invitations)
