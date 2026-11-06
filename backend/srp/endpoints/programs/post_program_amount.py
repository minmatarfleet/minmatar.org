"""POST {program_id}/amount - append a new amount to a program's history."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature
from srp.endpoints.programs.schemas import (
    SetProgramAmountRequest,
    ShipReimbursementProgramAmountResponse,
)
from srp.models import ShipReimbursementProgram, ShipReimbursementProgramAmount

PATH = "{int:program_id}/amount"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: ShipReimbursementProgramAmountResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_program_amount(
    request, program_id: int, payload: SetProgramAmountRequest
):
    denied = require_feature(request.user, "srp.programs.manage")
    if denied:
        return denied
    if payload.srp_value < 0:
        return 400, {"detail": "Amount cannot be negative"}
    program = ShipReimbursementProgram.objects.filter(id=program_id).first()
    if not program:
        return 404, {"detail": "Program not found"}
    amount = ShipReimbursementProgramAmount.objects.create(
        program=program, srp_value=payload.srp_value
    )
    return {
        "id": amount.id,
        "program_id": program.id,
        "srp_value": amount.srp_value,
        "created_at": amount.created_at.isoformat(),
    }
