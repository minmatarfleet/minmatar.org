"""GET "" — list SRP programs with current amount per ship type."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from onboarding.srp_gate import require_current_srp_onboarding
from srp.endpoints.programs.schemas import ShipReimbursementProgramResponse
from srp.models import ShipReimbursementProgram

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: List[ShipReimbursementProgramResponse],
        403: ErrorResponse,
    },
}


def get_srp_programs(request):
    if not request.user.has_perm("srp.view_evefleetshipreimbursement"):
        return 403, {
            "detail": "User missing permission srp.view_evefleetshipreimbursement"
        }
    denied = require_current_srp_onboarding(request)
    if denied:
        return denied

    programs = ShipReimbursementProgram.objects.select_related(
        "eve_type__eve_group__eve_category"
    ).all()

    return [
        {
            "id": entry.id,
            "eve_type": {
                "id": entry.eve_type.id,
                "name": entry.eve_type.name,
            },
            "eve_group": {
                "id": entry.eve_type.eve_group.id,
                "name": entry.eve_type.eve_group.name,
            },
            "eve_category": {
                "id": entry.eve_type.eve_group.eve_category.id,
                "name": entry.eve_type.eve_group.eve_category.name,
            },
            "current_amount": (
                {
                    "id": latest_amount.id,
                    "program_id": latest_amount.program_id,
                    "srp_value": latest_amount.srp_value,
                    "created_at": latest_amount.created_at.isoformat(),
                }
                if latest_amount
                else None
            ),
        }
        for entry in programs.order_by("eve_type__name", "id")
        for latest_amount in [
            entry.amounts.order_by("-created_at", "-id").first()
        ]
    ]
