"""GET history — chronological SRP program amount changes."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from onboarding.srp_gate import require_current_srp_onboarding
from srp.endpoints.programs.schemas import (
    ShipReimbursementProgramAmountResponse,
)
from srp.models import ShipReimbursementProgramAmount

PATH = "history"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: List[ShipReimbursementProgramAmountResponse],
        403: ErrorResponse,
    },
}


def get_srp_program_history(request):
    if not request.user.has_perm("srp.view_evefleetshipreimbursement"):
        return 403, {
            "detail": "User missing permission srp.view_evefleetshipreimbursement"
        }
    denied = require_current_srp_onboarding(request)
    if denied:
        return denied

    return [
        {
            "id": amount.id,
            "program_id": amount.program_id,
            "srp_value": amount.srp_value,
            "created_at": amount.created_at.isoformat(),
        }
        for amount in ShipReimbursementProgramAmount.objects.all().order_by(
            "-created_at", "-id"
        )
    ]
