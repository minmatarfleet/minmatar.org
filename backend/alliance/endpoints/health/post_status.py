"""POST /api/alliance/health/status — promote off trial or put on leave."""

from django.contrib.auth.models import User

from alliance.endpoints.health.helpers import require_health_view
from alliance.endpoints.health.schemas import (
    HealthStatusChangeRequest,
    HealthStatusChangeResponse,
)
from alliance.helpers.access import can_mutate_status, can_put_on_leave
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers import process_bulk_community_status_row
from groups.models import UserCommunityStatus

PATH = "status"
METHOD = "post"

ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: HealthStatusChangeResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}

_ACTIONS = {
    "promote": UserCommunityStatus.STATUS_ACTIVE,
    "leave": UserCommunityStatus.STATUS_ON_LEAVE,
}


def post_health_status(request, payload: HealthStatusChangeRequest):
    denied = require_health_view(request.user)
    if denied:
        return denied
    if payload.action not in _ACTIONS:
        return 400, ErrorResponse(detail="action must be promote or leave")
    target = User.objects.filter(pk=payload.user_id).first()
    if target is None:
        return 404, ErrorResponse(detail="User not found")
    if payload.action == "leave":
        allowed = can_put_on_leave(request.user, target)
    else:
        allowed = can_mutate_status(request.user, target)
    if not allowed:
        return 403, ErrorResponse(
            detail="Not allowed to change this member's community status"
        )
    new_status = _ACTIONS[payload.action]
    try:
        current = target.community_status.status
    except UserCommunityStatus.DoesNotExist:
        current = None
    if payload.action == "promote":
        if current != UserCommunityStatus.STATUS_TRIAL:
            return 400, ErrorResponse(
                detail="Promote is only valid for members currently on trial"
            )
    reason = (payload.reason or "").strip() or (
        "Promoted from trial via alliance health"
        if payload.action == "promote"
        else "Put on leave via alliance health"
    )
    result = process_bulk_community_status_row(
        {
            "username": target.username,
            "community_status": new_status,
            "reason": reason,
        },
        1,
        reason,
        changed_by_user_id=request.user.id,
    )
    applied = result[0]
    error = result[2]
    if error:
        return 400, ErrorResponse(detail=error)
    if not applied:
        return 400, ErrorResponse(detail="Status was not applied")
    return HealthStatusChangeResponse(
        user_id=target.id,
        status=new_status,
        detail="updated",
    )
