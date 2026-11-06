"""GET recalculate - preview what recalculating outstanding SRP changes."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature
from srp.endpoints.programs.schemas import RecalculationPreviewResponse
from srp.helpers import outstanding_recalculation_preview

PATH = "recalculate"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: RecalculationPreviewResponse, 403: ErrorResponse},
}


def get_recalculation_preview(request):
    denied = require_feature(request.user, "srp.programs.manage")
    if denied:
        return denied
    return outstanding_recalculation_preview()
