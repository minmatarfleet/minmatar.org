"""GET "/admin/metrics" - mentor metrics for learning managers."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import (
    ERRORS,
    handles_errors,
    require_manage,
)
from learning.mentors import metrics
from learning.mentors.schemas import MentorsMetricsResponse

PATH = "/admin/metrics"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Requests, mentors, coverage and impact for a period.",
    "auth": AuthBearer(),
    "response": {200: MentorsMetricsResponse, **ERRORS},
}


@handles_errors
def get_admin_metrics(request, period: int = 90):
    require_manage(request.user)
    period = period if period in (30, 90, 365) else 90
    return 200, metrics.compute(period)
