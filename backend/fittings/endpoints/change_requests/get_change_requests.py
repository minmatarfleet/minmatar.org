"""GET "" - the doctrine/fitting change-request review queue."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from fittings.endpoints.change_requests.schemas import ChangeRequestResponse
from fittings.helpers.change_request_api import (
    REQUEST_MODELS,
    can_edit_doctrines,
    serialize_request,
)

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[ChangeRequestResponse], 403: ErrorResponse},
}


def get_change_requests(request, status: str = "pending"):
    """status=pending lists open requests; anything else the latest 25."""
    if not can_edit_doctrines(request.user):
        return 403, {"detail": "You cannot see doctrine change requests"}
    rows = []
    for kind, model in REQUEST_MODELS.items():
        queryset = model.objects.select_related(
            "submitted_by", "reviewed_by"
        ).order_by("-submitted_at")
        queryset = (
            queryset.filter(status="pending")
            if status == "pending"
            else queryset[:25]
        )
        rows.extend(
            serialize_request(request.user, kind, change_request)
            for change_request in queryset
        )
    rows.sort(key=lambda row: row["submitted_at"], reverse=True)
    return rows
