"""GET /api/alliance/health/leave"""

from typing import Literal

from django.http import HttpResponse
from ninja import Query

from alliance.endpoints.health.helpers import require_snapshot
from alliance.endpoints.health.schemas import (
    HealthLeaveResponse,
    leave_csv_lines,
    leave_from_payload,
)
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature

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


def get_health_leave(
    request,
    response_format: Literal["json", "csv"] = Query("json", alias="format"),
):
    denied = require_feature(request.user, "alliance.health")
    if denied:
        return denied
    snap, err = require_snapshot()
    if err:
        return err
    payload = leave_from_payload(snap.payload)
    if response_format == "csv":
        body = leave_csv_lines(payload.pilots)
        response = HttpResponse(body, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="on_leave.csv"'
        return response
    return payload
