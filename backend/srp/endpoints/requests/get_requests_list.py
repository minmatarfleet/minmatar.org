"""GET \"\" — list SRP requests (filtered, paginated)."""

from ninja import Query

from app.errors import ErrorResponse
from authentication import AuthBearer
from onboarding.srp_gate import require_current_srp_onboarding
from srp.endpoints.requests.helpers import (
    reimbursement_to_response,
    visible_reimbursements_qs,
)
from srp.endpoints.requests.schemas import (
    SrpRequestListSchema,
    SrpRequestResponse,
)

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: SrpRequestListSchema, 403: ErrorResponse},
    "description": "List SRP requests visible to the caller with optional filters.",
}

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def list_srp_requests(
    request,
    fleet_id: int | None = None,
    status: str | None = None,
    user_id: int | None = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    if not request.user.has_perm("srp.view_evefleetshipreimbursement"):
        return 403, {
            "detail": "User missing permission srp.view_evefleetshipreimbursement"
        }

    denied = require_current_srp_onboarding(request)
    if denied:
        return denied

    qs = visible_reimbursements_qs(
        request.user,
        fleet_id=fleet_id,
        status=status,
        user_id=user_id,
    ).order_by("-id")

    total = qs.count()
    page = qs[offset : offset + limit]
    items = [
        SrpRequestResponse.model_validate(reimbursement_to_response(r))
        for r in page
    ]

    return SrpRequestListSchema(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
