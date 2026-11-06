"""put_contract_expectation"""

from app.errors import ErrorResponse
from authentication import AuthBearer
from market.models import (
    EveMarketContractExpectation,
)
from market.endpoints.hubs.common import (
    set_fitting_tracked,
)
from market.endpoints.hubs.schemas import (
    TrackedRequest,
    FittingExpectationRow,
)

PATH = "/hubs/{location_id}/expectations/contracts/{fitting_id}"
METHOD = "put"
ROUTE_SPEC = {
    "summary": "Track or untrack a doctrine fitting's contracts at a hub",
    "auth": AuthBearer(),
    "response": {
        200: FittingExpectationRow,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def put_contract_expectation(
    request, location_id: int, fitting_id: int, payload: TrackedRequest
):
    return set_fitting_tracked(
        request,
        location_id,
        fitting_id,
        payload.tracked,
        EveMarketContractExpectation,
        "Contract expectation",
    )
