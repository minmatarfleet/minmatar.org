"""GET /api/alliance/health/attention"""

from typing import Literal

from alliance.endpoints.health.helpers import require_snapshot
from alliance.endpoints.health.schemas import (
    HealthAttentionResponse,
    attention_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature
from ninja import Query

PATH = "attention"
METHOD = "get"

ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: HealthAttentionResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        503: ErrorResponse,
    },
}

VALID_BUCKETS = frozenset({"fading", "dark", "seasonal"})


def get_health_attention(
    request,
    bucket: Literal["fading", "dark", "seasonal"] = Query("fading"),
):
    denied = require_feature(request.user, "alliance.health")
    if denied:
        return denied
    if bucket not in VALID_BUCKETS:
        return 400, ErrorResponse(
            detail="bucket must be fading, dark, or seasonal"
        )
    snap, err = require_snapshot()
    if err:
        return err
    return attention_from_payload(snap.payload, bucket)
