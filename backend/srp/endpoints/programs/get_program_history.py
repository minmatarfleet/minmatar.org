"""GET history — chronological SRP program amount changes."""

from typing import List

from srp.endpoints.programs.schemas import (
    ShipReimbursementProgramAmountResponse,
)
from srp.models import ShipReimbursementProgramAmount

PATH = "history"
METHOD = "get"
ROUTE_SPEC = {
    "response": {200: List[ShipReimbursementProgramAmountResponse]},
}


def get_srp_program_history(request):
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
