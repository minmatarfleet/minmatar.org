"""GET "/invitations/mine" - the signed-in pilot's waiting invites."""

from typing import List

from django.utils import timezone
from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.invitations.schemas import InvitationSchema
from tribes.endpoints.invitations.serializers import serialize_invitations
from tribes.models import TribeGroupInvitation

PATH = "/invitations/mine"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Your waiting tribe group invites.",
    "response": {200: List[InvitationSchema]},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Invitations"])


def get_my_invitations(request):
    invitations = (
        TribeGroupInvitation.objects.filter(
            user=request.user,
            status=TribeGroupInvitation.STATUS_PENDING,
            expires_at__gt=timezone.now(),
        )
        .select_related(
            "tribe_group__tribe",
            "user__eveplayer__primary_character",
            "invited_by__eveplayer__primary_character",
        )
        .order_by("-created_at")
    )
    return 200, serialize_invitations(invitations)


router.get(PATH, **ROUTE_SPEC)(get_my_invitations)
