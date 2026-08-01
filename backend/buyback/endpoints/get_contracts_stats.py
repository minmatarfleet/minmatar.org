"""GET /contracts/stats – buyback in/out aggregate metrics."""

from datetime import timedelta
from typing import Optional

from django.db.models import Sum
from django.utils import timezone
from ninja import Router

from buyback.endpoints.schemas import BuybackContractsStatsResponse
from buyback.models import BuybackContract

router = Router(tags=["Buyback"])

METRICS_WINDOW_DAYS = 30


def _average_processing_seconds(since) -> Optional[int]:
    pairs = (
        BuybackContract.objects.finished()
        .filter(
            date_completed__gte=since,
            date_issued__isnull=False,
            date_completed__isnull=False,
        )
        .values_list("date_issued", "date_completed")
    )
    durations = [
        (completed - issued).total_seconds()
        for issued, completed in pairs
        if issued is not None and completed is not None
    ]
    if not durations:
        return None
    return int(round(sum(durations) / len(durations)))


def compute_contracts_stats() -> BuybackContractsStatsResponse:
    since = timezone.now() - timedelta(days=METRICS_WINDOW_DAYS)

    outstanding = BuybackContract.objects.filter(status="outstanding")
    outstanding_isk = outstanding.aggregate(total=Sum("price"))["total"] or 0

    finished = BuybackContract.objects.finished().filter(
        date_completed__gte=since
    )
    finished_isk = finished.aggregate(total=Sum("price"))["total"] or 0

    return BuybackContractsStatsResponse(
        outstanding_count=outstanding.count(),
        outstanding_isk=int(outstanding_isk),
        finished_count=finished.count(),
        finished_isk=int(finished_isk),
        average_processing_seconds=_average_processing_seconds(since),
        window_days=METRICS_WINDOW_DAYS,
    )


@router.get(
    "/stats",
    description=(
        "Buyback metrics: outstanding contracts/ISK (in), finished "
        f"contracts/ISK over the last {METRICS_WINDOW_DAYS} days (out), "
        "and average processing time."
    ),
    response=BuybackContractsStatsResponse,
)
def get_contracts_stats(request):
    return compute_contracts_stats()
