"""GET /api/alliance/health/trials"""

from typing import Literal

from django.http import HttpResponse
from ninja import Query

from alliance.endpoints.health.helpers import require_snapshot
from alliance.endpoints.health.schemas import (
    HealthTrialsResponse,
    trial_csv_lines,
    trials_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature

PATH = "trials"
METHOD = "get"

ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: HealthTrialsResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        503: ErrorResponse,
    },
}

VALID_BUCKETS = frozenset({"approve", "too_early", "fail", "nudge"})


def get_health_trials(
    request,
    bucket: Literal["approve", "too_early", "fail", "nudge"] = Query(
        "approve"
    ),
    response_format: Literal["json", "csv"] = Query("json", alias="format"),
):
    denied = require_feature(request.user, "alliance.health")
    if denied:
        return denied
    if bucket not in VALID_BUCKETS:
        return 400, ErrorResponse(
            detail="bucket must be approve, too_early, fail, or nudge"
        )
    snap, err = require_snapshot()
    if err:
        return err
    payload = trials_from_payload(snap.payload, bucket)
    if response_format == "csv":
        if bucket != "approve":
            return 400, ErrorResponse(
                detail="CSV export is only available for the approve bucket"
            )
        body = trial_csv_lines(payload.pilots)
        response = HttpResponse(body, content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="trial_approve.csv"'
        )
        return response
    return payload
