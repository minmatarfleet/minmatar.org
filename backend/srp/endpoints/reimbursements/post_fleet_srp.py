"""POST \"\" — create SRP request (deprecated; use POST /api/srp/v2/requests)."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from srp.endpoints.reimbursements.schemas import (
    CreateEveFleetReimbursementRequest,
    EveFleetReimbursementResponse,
)
from srp.endpoints.requests.post_request import create_srp_request

PATH = ""
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetReimbursementResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "deprecated": True,
    "description": "Deprecated. Use POST /api/srp/v2/requests.",
}


def create_fleet_srp(request, payload: CreateEveFleetReimbursementRequest):
    return create_srp_request(request, payload)
