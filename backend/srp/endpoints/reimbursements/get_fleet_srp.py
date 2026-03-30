"""GET \"\" — list SRP requests (deprecated; use GET /api/srp/v2/requests)."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from srp.endpoints.reimbursements.schemas import EveFleetReimbursementResponse
from srp.endpoints.requests.helpers import (
    reimbursement_to_response,
    visible_reimbursements_qs,
)

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetReimbursementResponse], 403: ErrorResponse},
    "deprecated": True,
    "description": "Deprecated. Use GET /api/srp/v2/requests (paginated).",
}


def get_fleet_srp(
    request,
    fleet_id: int | None = None,
    status: str | None = None,
    user_id: int | None = None,
):
    if not request.user.has_perm("srp.view_evefleetshipreimbursement"):
        return 403, {
            "detail": "User missing permission srp.view_evefleetshipreimbursement"
        }

    qs = visible_reimbursements_qs(
        request.user,
        fleet_id=fleet_id,
        status=status,
        user_id=user_id,
    ).order_by("-id")

    return [
        EveFleetReimbursementResponse.model_validate(
            reimbursement_to_response(r)
        )
        for r in qs
    ]
