"""POST "" - add a hull to SRP with its first amount."""

from eveuniverse.models import EveType

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature
from srp.endpoints.programs.schemas import (
    CreateProgramRequest,
    ShipReimbursementProgramAmountResponse,
)
from srp.models import ShipReimbursementProgram, ShipReimbursementProgramAmount

SHIP_CATEGORY_ID = 6

PATH = ""
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: ShipReimbursementProgramAmountResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
}


def post_program(request, payload: CreateProgramRequest):
    denied = require_feature(request.user, "srp.programs.manage")
    if denied:
        return denied
    if payload.srp_value < 0:
        return 400, {"detail": "Amount cannot be negative"}
    ship = (
        EveType.objects.filter(
            id=payload.eve_type_id,
            eve_group__eve_category_id=SHIP_CATEGORY_ID,
        )
        .select_related("eve_group")
        .first()
    )
    if ship is None:
        return 400, {"detail": "Not a ship"}
    if ShipReimbursementProgram.objects.filter(eve_type=ship).exists():
        return 400, {"detail": f"{ship.name} already has an SRP amount"}
    program = ShipReimbursementProgram.objects.create(eve_type=ship)
    amount = ShipReimbursementProgramAmount.objects.create(
        program=program, srp_value=payload.srp_value
    )
    return {
        "id": amount.id,
        "program_id": program.id,
        "srp_value": amount.srp_value,
        "created_at": amount.created_at.isoformat(),
    }
