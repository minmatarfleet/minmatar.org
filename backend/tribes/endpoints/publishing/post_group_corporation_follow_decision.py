"""POST "/groups/{group_id}/corporation-follows/{follow_id}" - a manager
approves or revokes a corporation's follow of the group's fleet posts."""

from typing import List

from django.utils import timezone
from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints.publishing.corporation_follows import (
    serialize_corporation_follows,
)
from tribes.endpoints.publishing.schemas import (
    CorporationFollowDecision,
    CorporationFollowDecisionRequest,
    GroupCorporationFollowSchema,
)
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupCorporationFollow

PATH = "/groups/{group_id}/corporation-follows/{follow_id}"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Approve or revoke a corporation's follow of the group.",
    "description": (
        "Managers of the group only. Approved: the group's roundup, quiet "
        "pre-ping and start ping (with @here) are copied to the "
        "corporation's channel. Revoked: nothing more is copied."
    ),
    "response": {
        200: List[GroupCorporationFollowSchema],
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Publishing"])

STATUS_FOR = {
    CorporationFollowDecision.APPROVE: (
        TribeGroupCorporationFollow.STATUS_APPROVED
    ),
    CorporationFollowDecision.REVOKE: TribeGroupCorporationFollow.STATUS_REVOKED,
}


def post_group_corporation_follow_decision(
    request,
    group_id: int,
    follow_id: int,
    payload: CorporationFollowDecisionRequest,
):
    group = TribeGroup.objects.filter(pk=group_id).first()
    if group is None:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, group):
        return 403, {"detail": "Only the group's managers can change this."}
    follow = TribeGroupCorporationFollow.objects.filter(
        pk=follow_id, tribe_group=group
    ).first()
    if follow is None:
        return 404, {"detail": "Follow not found."}
    follow.status = STATUS_FOR[payload.decision]
    follow.decided_by = request.user
    follow.decided_at = timezone.now()
    follow.save(
        update_fields=["status", "decided_by", "decided_at", "updated_at"]
    )
    return 200, serialize_corporation_follows(group)


router.post(PATH, **ROUTE_SPEC)(post_group_corporation_follow_decision)
