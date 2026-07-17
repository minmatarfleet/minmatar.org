"""GET /{int:request_id} — single SRP request."""

from groups.helpers.feature_access import require_feature
from app.errors import ErrorResponse
from authentication import AuthBearer
from onboarding.srp_gate import require_current_srp_onboarding
from srp.endpoints.requests.helpers import (
    can_view_request,
    reimbursement_to_response,
)
from srp.endpoints.requests.schemas import SrpRequestResponse
from srp.models import EveFleetShipReimbursement

PATH = "/{int:request_id}"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: SrpRequestResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_srp_request(request, request_id: int):
    denied = require_feature(request.user, "srp.view")
    if denied:
        return denied

    denied = require_current_srp_onboarding(request)
    if denied:
        return denied

    reimbursement = EveFleetShipReimbursement.objects.filter(
        id=request_id
    ).first()
    if not reimbursement:
        return 404, {"detail": "Reimbursement does not exist"}

    if not can_view_request(request.user, reimbursement):
        return 403, {
            "detail": "User missing permission srp.change_evefleetshipreimbursement"
        }

    return SrpRequestResponse.model_validate(
        reimbursement_to_response(reimbursement)
    )
