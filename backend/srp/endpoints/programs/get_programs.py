"""GET "" — list SRP programs with current amount per ship type."""

from groups.helpers.feature_access import can_use_feature, require_feature
from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from onboarding.srp_gate import require_current_srp_onboarding
from srp.endpoints.programs.schemas import ShipReimbursementProgramResponse
from srp.helpers import outstanding_counts_by_hull
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
    denied = require_feature(request.user, "srp.view")
    if denied:
        return 403, {
            "detail": "User missing permission srp.view_evefleetshipreimbursement"
        }
    # Program managers edit amounts on the site: no onboarding wall for
    # them. Superusers hold every permission, so only explicit assignees
    # skip it (same rule as bypass_srp_onboarding).
    is_manager = not request.user.is_superuser and can_use_feature(
        request.user, "srp.programs.manage"
    )
    if not is_manager:
        denied = require_current_srp_onboarding(request)
        if denied:
            return denied

    counts = (
        outstanding_counts_by_hull()
        if can_use_feature(request.user, "srp.programs.manage")
        else {}
    )
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
            "open_requests": counts.get(entry.eve_type_id, {}).get("open", 0),
            "stale_requests": counts.get(entry.eve_type_id, {}).get(
                "stale", 0
            ),
        }
        for entry in programs.order_by("eve_type__name", "id")
        for latest_amount in [
            entry.amounts.order_by("-created_at", "-id").first()
        ]
    ]
