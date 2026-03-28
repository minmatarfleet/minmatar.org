"""GET overview — pending SRP queue and average approval latency (last 90 days)."""

from typing import Optional

from django.db.models import Count, Sum
from app.errors import ErrorResponse
from authentication import AuthBearer
from pydantic import BaseModel
from srp.helpers import average_payout_seconds_approved_last_days
from srp.models import EveFleetShipReimbursement

PATH = "overview"
METHOD = "get"


class SrpStatsOverviewResponse(BaseModel):
    pending_requests: int
    pending_total: int
    average_response_days: Optional[float] = None


ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: SrpStatsOverviewResponse, 403: ErrorResponse},
}


def get_srp_stats_overview(request):
    if not request.user.has_perm("srp.view_evefleetshipreimbursement"):
        return 403, {
            "detail": "User missing permission srp.view_evefleetshipreimbursement"
        }

    pending = EveFleetShipReimbursement.objects.filter(status="pending")
    pending_agg = pending.aggregate(
        cnt=Count("id"),
        amt=Sum("amount"),
    )
    pending_requests = int(pending_agg["cnt"] or 0)
    pending_total = int(pending_agg["amt"] or 0)

    average_seconds, sample_size = average_payout_seconds_approved_last_days(
        90
    )
    average_response_days = None
    if sample_size:
        average_response_days = average_seconds / 86400.0

    return SrpStatsOverviewResponse(
        pending_requests=pending_requests,
        pending_total=pending_total,
        average_response_days=average_response_days,
    )
