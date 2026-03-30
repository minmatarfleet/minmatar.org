"""PATCH /{reimbursement_id} — update SRP (deprecated; use PATCH /api/srp/v2/requests/{id})."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from srp.endpoints.reimbursements.schemas import (
    SrpPatchResult,
    UpdateEveFleetReimbursementRequest,
)
from srp.endpoints.requests.patch_request import patch_srp_request

PATH = "/{int:reimbursement_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: SrpPatchResult, 403: ErrorResponse, 404: ErrorResponse},
    "deprecated": True,
    "description": "Deprecated. Use PATCH /api/srp/v2/requests/{id}.",
}


def update_fleet_srp(
    request, reimbursement_id: int, payload: UpdateEveFleetReimbursementRequest
):
    return patch_srp_request(request, reimbursement_id, payload)
