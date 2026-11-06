"""POST {kind}/{id}/review - approve, reject or cancel a change request."""

from django.core.exceptions import ValidationError

from app.errors import ErrorResponse
from authentication import AuthBearer
from fittings.endpoints.change_requests.schemas import (
    ChangeRequestResponse,
    ReviewRequest,
)
from fittings.helpers.change_request_api import (
    REQUEST_MODELS,
    can_edit_doctrines,
    can_review_request,
    serialize_request,
)
from fittings.helpers.doctrine_changes import (
    approve_doctrine_change_request,
    cancel_doctrine_change_request,
    reject_doctrine_change_request,
)
from fittings.helpers.fitting_changes import (
    approve_fitting_change_request,
    cancel_fitting_change_request,
    reject_fitting_change_request,
)

PATH = "{str:kind}/{int:request_id}/review"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: ChangeRequestResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
}

ACTIONS = {
    "doctrine": {
        "approve": approve_doctrine_change_request,
        "reject": reject_doctrine_change_request,
        "cancel": cancel_doctrine_change_request,
    },
    "fitting": {
        "approve": approve_fitting_change_request,
        "reject": reject_fitting_change_request,
        "cancel": cancel_fitting_change_request,
    },
}


def post_review_change_request(
    request, kind: str, request_id: int, payload: ReviewRequest
):
    if kind not in REQUEST_MODELS or payload.action not in ACTIONS[kind]:
        return 400, {"detail": "Unknown request kind or action"}
    if not can_edit_doctrines(request.user):
        return 403, {"detail": "You cannot review change requests"}
    change_request = REQUEST_MODELS[kind].objects.filter(pk=request_id).first()
    if not change_request:
        return 404, {"detail": "Change request not found"}

    reviewer = can_review_request(request.user, kind, change_request.tier)
    if payload.action == "cancel":
        allowed = reviewer or change_request.submitted_by_id == request.user.id
    else:
        allowed = reviewer
    if not allowed:
        return 403, {"detail": "You cannot do that to this request"}

    action = ACTIONS[kind][payload.action]
    try:
        if payload.action == "cancel":
            action(change_request, request.user)
        else:
            action(change_request, request.user, payload.review_note)
    except (ValueError, ValidationError) as exc:
        return 409, {"detail": str(exc)}
    change_request.refresh_from_db()
    return serialize_request(request.user, kind, change_request)
