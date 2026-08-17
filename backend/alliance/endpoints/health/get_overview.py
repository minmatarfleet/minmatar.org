"""GET /api/alliance/health/overview"""

from datetime import timedelta

from alliance.endpoints.health.helpers import (
    require_health_view,
    require_snapshot,
    viewer_context,
)
from alliance.endpoints.health.schemas import (
    HealthOverviewResponse,
    overview_from_payload,
)
from alliance.helpers.health import snapshot_before
from app.errors import ErrorResponse
from authentication import AuthBearer

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
    denied = require_health_view(request.user)
    if denied:
        return denied
    snap, err = require_snapshot()
    if err:
        return err
    prior = snapshot_before(snap.computed_at - timedelta(days=30))
    prior_payload = None
    if prior is not None and prior.pk != snap.pk:
        prior_payload = prior.payload
    return overview_from_payload(
        snap.payload, viewer_context(request.user), prior_payload
    )
