"""GET /api/alliance/health/cohorts"""

from alliance.endpoints.health.helpers import (
    require_health_view,
    require_snapshot,
)
from alliance.endpoints.health.schemas import (
    HealthCohortsResponse,
    cohorts_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer

PATH = "cohorts"
METHOD = "get"

ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: HealthCohortsResponse,
        403: ErrorResponse,
        503: ErrorResponse,
    },
}


def get_health_cohorts(request):
    denied = require_health_view(request.user)
    if denied:
        return denied
    snap, err = require_snapshot()
    if err:
        return err
    return cohorts_from_payload(snap.payload)
