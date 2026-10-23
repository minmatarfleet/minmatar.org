"""GET "/{tribe_id}/groups/{group_id}/invitations" - the chief's invite list."""

from datetime import timedelta
from typing import List

from django.db.models import Q
from django.utils import timezone

from authentication import AuthBearer
from tribes.endpoints.invitations.schemas import InvitationSchema
from tribes.endpoints.invitations.serializers import serialize_invitations
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupInvitation

# Answered invites stay on the list this long.
ANSWERED_DAYS = 30

PATH = "/{tribe_id}/groups/{group_id}/invitations"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Invites to a tribe group: waiting, and answered in 30 days.",
    "response": {200: List[InvitationSchema], 403: dict, 404: dict},
    "auth": AuthBearer(),
}


def get_group_invitations(request, tribe_id: int, group_id: int):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {
            "detail": "Only people who manage this group see its invites."
        }

    since = timezone.now() - timedelta(days=ANSWERED_DAYS)
    invitations = (
        TribeGroupInvitation.objects.filter(tribe_group=tg)
        .filter(
            Q(status=TribeGroupInvitation.STATUS_PENDING)
            | Q(responded_at__gte=since)
        )
        .select_related(
            "tribe_group__tribe",
            "user__eveplayer__primary_character",
            "invited_by__eveplayer__primary_character",
        )
        .order_by("-created_at")
    )
    return 200, serialize_invitations(invitations)
