"""GET /api/alliance/health/corporations"""

from alliance.endpoints.health.helpers import (
    require_health_view,
    require_snapshot,
)
from alliance.endpoints.health.schemas import (
    HealthCorporationsResponse,
    corporations_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer

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
    denied = require_health_view(request.user)
    if denied:
        return denied
    snap, err = require_snapshot()
    if err:
        return err
    return corporations_from_payload(snap.payload)
