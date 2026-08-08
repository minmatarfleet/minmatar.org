"""GET /api/alliance/health/overview"""

from alliance.endpoints.health.helpers import require_snapshot
from alliance.endpoints.health.schemas import (
    HealthOverviewResponse,
    overview_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature

PATH = "overview"
METHOD = "get"

ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: HealthOverviewResponse,
        403: ErrorResponse,
        503: ErrorResponse,
    },
}


def get_health_overview(request):
    denied = require_feature(request.user, "alliance.health")
    if denied:
        return denied
    snap, err = require_snapshot()
    if err:
        return err
    return overview_from_payload(snap.payload)
