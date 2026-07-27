"""GET /contracts/stats – aggregate freight contract metrics for the active list UI."""

from datetime import timedelta
from typing import Optional

from django.db.models import Q
from django.utils import timezone
from ninja import Router

from eveonline.models import EveCharacter
from freight.models import FreightContract, FREIGHT_CORPORATION_ID
from freight.endpoints.schemas import FreightContractsStatsResponse

router = Router(tags=["Freight"])

METRICS_WINDOW_DAYS = 30


def _active_haulers_count(since) -> int:
    """Distinct haulers active in the metrics window.

    Prefer collapsing alts to one User when linked. Acceptors without a site
    user (or missing EveCharacter row) still count once by acceptor_id so the
    metric matches who appears in the servicing column.
    """
    acceptor_ids = {
        int(aid)
        for aid in FreightContract.objects.filter(acceptor_id__isnull=False)
        .exclude(acceptor_id=FREIGHT_CORPORATION_ID)
        .exclude(acceptor_id=0)
        .filter(
            Q(status="finished", date_completed__gte=since)
            | Q(status="in_progress")
        )
        .values_list("acceptor_id", flat=True)
        if aid
    }
    if not acceptor_ids:
        return 0

    chars = EveCharacter.objects.filter(
        character_id__in=acceptor_ids,
    ).select_related("user", "token__user")
    char_by_id = {c.character_id: c for c in chars}

    hauler_keys: set[tuple[str, int]] = set()
    for acceptor_id in acceptor_ids:
        char = char_by_id.get(acceptor_id)
        if char:
            user = char.user or (
                char.token.user if getattr(char, "token", None) else None
            )
            if user:
                hauler_keys.add(("user", user.id))
                continue
        hauler_keys.add(("char", acceptor_id))
    return len(hauler_keys)


def _average_delivery_seconds(since) -> Optional[int]:
    """Mean (date_completed - date_issued) for finished contracts in the window."""
    pairs = (
        FreightContract.objects.finished()
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


def compute_contracts_stats() -> FreightContractsStatsResponse:
    since = timezone.now() - timedelta(days=METRICS_WINDOW_DAYS)

    return FreightContractsStatsResponse(
        active_count=FreightContract.objects.active().count(),
        average_delivery_seconds=_average_delivery_seconds(since),
        active_haulers_count=_active_haulers_count(since),
        window_days=METRICS_WINDOW_DAYS,
    )


@router.get(
    "/stats",
    description=(
        "Aggregate freight metrics: active contract count (outstanding + "
        "in progress), average delivery time over the last "
        f"{METRICS_WINDOW_DAYS} days of finished contracts, and distinct "
        "active haulers in that window."
    ),
    response=FreightContractsStatsResponse,
)
def get_contracts_stats(request):
    return compute_contracts_stats()
