"""GET /api/alliance/health/trials"""

from typing import Literal

from django.http import HttpResponse
from ninja import Query

from alliance.endpoints.health.helpers import (
    require_health_view,
    require_snapshot,
)
from alliance.endpoints.health.schemas import (
    HealthTrialsResponse,
    TrialBucket,
    trial_csv_lines,
    trials_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer

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

VALID_BUCKETS = frozenset(
    {
        "current",
        "passing",
        "failing",
        "evaluating",
        "add",
        "remove",
        "flagged",
        "approve",
        "too_early",
        "fail",
        "nudge",
    }
)
CSV_BUCKETS = frozenset({"approve", "remove"})


def get_health_trials(
    request,
    bucket: TrialBucket = Query("current"),
    response_format: Literal["json", "csv"] = Query("json", alias="format"),
):
    denied = require_health_view(request.user)
    if denied:
        return denied
    if bucket not in VALID_BUCKETS:
        return 400, ErrorResponse(
            detail="bucket must be current, passing, failing, evaluating, or a legacy hygiene bucket"
        )
    snap, err = require_snapshot()
    if err:
        return err
    payload = trials_from_payload(snap.payload, bucket)
    if response_format == "csv":
        if bucket not in CSV_BUCKETS:
            return 400, ErrorResponse(
                detail="CSV export is only available for remove/approve"
            )
        body = trial_csv_lines(payload.pilots)
        response = HttpResponse(body, content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="trial_approve.csv"'
        )
        return response
    return payload
