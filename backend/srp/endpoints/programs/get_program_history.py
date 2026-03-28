"""GET history — chronological SRP program amount changes."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
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
    if not request.user.has_perm("srp.view_shipreimbursementprogramamount"):
        return 403, {
            "detail": "User missing permission srp.view_shipreimbursementprogramamount"
        }

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
