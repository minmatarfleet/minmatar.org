"""GET /api/alliance/health/onboarding"""

from typing import Literal

from ninja import Query

from alliance.endpoints.health.helpers import (
    require_health_view,
    require_snapshot,
)
from alliance.endpoints.health.schemas import (
    HealthOnboardingResponse,
    onboarding_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer

PATH = "onboarding"
METHOD = "get"

ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: HealthOnboardingResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        503: ErrorResponse,
    },
}

VALID_BUCKETS = frozenset({"first_week", "more_fleets"})


def get_health_onboarding(
    request,
    bucket: Literal["first_week", "more_fleets"] = Query("first_week"),
):
    denied = require_health_view(request.user)
    if denied:
        return denied
    if bucket not in VALID_BUCKETS:
        return 400, ErrorResponse(
            detail="bucket must be first_week or more_fleets"
        )
    snap, err = require_snapshot()
    if err:
        return err
    return onboarding_from_payload(snap.payload, bucket)
