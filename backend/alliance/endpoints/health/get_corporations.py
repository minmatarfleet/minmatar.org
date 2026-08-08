"""GET /api/alliance/health/corporations"""

from alliance.endpoints.health.helpers import require_snapshot
from alliance.endpoints.health.schemas import (
    HealthCorporationsResponse,
    corporations_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature

PATH = "corporations"
METHOD = "get"

ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: HealthCorporationsResponse,
        403: ErrorResponse,
        503: ErrorResponse,
    },
}


def get_health_corporations(request):
    denied = require_feature(request.user, "alliance.health")
    if denied:
        return denied
    snap, err = require_snapshot()
    if err:
        return err
    return corporations_from_payload(snap.payload)
