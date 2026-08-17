"""GET /api/alliance/health/leave"""

from typing import Literal

from django.http import HttpResponse
from ninja import Query

from alliance.endpoints.health.helpers import (
    require_health_view,
    require_snapshot,
)
from alliance.endpoints.health.schemas import (
    HealthLeaveResponse,
    LeaveBucket,
    leave_csv_lines,
    leave_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer

PATH = "leave"
METHOD = "get"

ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: HealthLeaveResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        503: ErrorResponse,
    },
}

VALID_BUCKETS = frozenset(
    {"current", "inactive", "returning", "add", "remove", "flagged"}
)
CSV_BUCKETS = frozenset({"add", "remove", "returning"})


def get_health_leave(
    request,
    bucket: LeaveBucket = Query("current"),
    response_format: Literal["json", "csv"] = Query("json", alias="format"),
):
    denied = require_health_view(request.user)
    if denied:
        return denied
    if bucket not in VALID_BUCKETS:
        return 400, ErrorResponse(
            detail="bucket must be current, inactive, returning, add, remove, or flagged"
        )
    snap, err = require_snapshot()
    if err:
        return err
    payload = leave_from_payload(snap.payload, bucket)
    if response_format == "csv":
        if bucket not in CSV_BUCKETS:
            return 400, ErrorResponse(
                detail="CSV export is only available for add or remove"
            )
        body = leave_csv_lines(payload.pilots, bucket=bucket)
        response = HttpResponse(body, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="on_leave.csv"'
        return response
    return payload
