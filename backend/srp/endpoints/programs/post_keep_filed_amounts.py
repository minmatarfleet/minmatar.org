"""POST recalculate/keep - keep a hull's requests at their filed amounts."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature
from srp.endpoints.programs.schemas import RecalculationResultResponse
from srp.helpers import keep_filed_amounts

PATH = "recalculate/keep"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: RecalculationResultResponse, 403: ErrorResponse},
}


def post_keep_filed_amounts(request, ship_type_id: int):
    """The hull's requests stop showing as filed at an old amount."""
    denied = require_feature(request.user, "srp.programs.manage")
    if denied:
        return denied
    return keep_filed_amounts(ship_type_id)
