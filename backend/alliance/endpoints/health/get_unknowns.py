"""GET /api/alliance/health/unknowns"""

from alliance.endpoints.health.helpers import (
    require_health_view,
    require_snapshot,
)
from alliance.endpoints.health.schemas import (
    HealthUnknownsResponse,
    unknown_characters_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer

PATH = "unknowns"
METHOD = "get"

ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: HealthUnknownsResponse,
        403: ErrorResponse,
        503: ErrorResponse,
    },
}


def get_health_unknowns(request):
    denied = require_health_view(request.user)
    if denied:
        return denied
    snap, err = require_snapshot()
    if err:
        return err
    return HealthUnknownsResponse(
        computed_at=snap.payload.get("computed_at")
        or snap.computed_at.isoformat(),
        characters=unknown_characters_from_payload(snap.payload),
    )
