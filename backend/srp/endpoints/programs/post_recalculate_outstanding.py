"""POST recalculate - rewrite every outstanding SRP request's amount."""

from typing import Optional

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature
from srp.endpoints.programs.schemas import RecalculationResultResponse
from srp.helpers import recalculate_outstanding

PATH = "recalculate"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: RecalculationResultResponse, 403: ErrorResponse},
}


def post_recalculate_outstanding(request, ship_type_id: Optional[int] = None):
    """With ship_type_id: only that hull's requests filed at an old amount."""
    denied = require_feature(request.user, "srp.programs.manage")
    if denied:
        return denied
    return recalculate_outstanding(ship_type_id=ship_type_id)
