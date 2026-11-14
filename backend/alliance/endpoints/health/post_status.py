"""POST /api/alliance/health/status — promote, put on leave, or restore."""

from django.contrib.auth.models import User

from alliance.endpoints.health.helpers import require_health_view
from alliance.endpoints.health.schemas import (
    HealthStatusChangeRequest,
    HealthStatusChangeResponse,
)
from alliance.helpers.status_change import change_community_status
from app.errors import ErrorResponse
from authentication import AuthBearer

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


def post_health_status(request, payload: HealthStatusChangeRequest):
    denied = require_health_view(request.user)
    if denied:
        return denied
    target = User.objects.filter(pk=payload.user_id).first()
    if target is None:
        return 404, ErrorResponse(detail="User not found")
    result = change_community_status(
        request.user, target, payload.action, payload.reason
    )
    if result.error:
        return result.code, ErrorResponse(detail=result.error)
    return HealthStatusChangeResponse(
        user_id=target.id,
        status=result.status,
        detail="updated",
    )
