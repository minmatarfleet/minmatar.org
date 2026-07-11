"""Market price helpers for implant and item valuation."""

from datetime import timedelta

from django.db.models import OuterRef, Subquery, Sum
from django.utils import timezone

from eveonline.models import EveLocation
from eveuniverse.models import EveMarketPrice
from market.models.history import EveMarketItemHistory

JITA_REGION_ID = 10000002
VOLUME_LOOKBACK_DAYS = 90


def _baseline_region_id() -> int:
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline and baseline.region_id:
        return baseline.region_id
    return JITA_REGION_ID


def get_prices_by_type_id(type_ids: list[int]) -> dict[int, int]:
    """
    Return Jita-baseline ISK prices for type IDs.

    Uses the price_baseline location's region history when configured,
    otherwise falls back to eveuniverse EveMarketPrice.average_price.
    """
    if not type_ids:
        return {}

    unique_ids = list({int(tid) for tid in type_ids})
    prices: dict[int, int] = {}

    region_id = _baseline_region_id()

    latest_date = (
        EveMarketItemHistory.objects.filter(
            region_id=region_id,
            item_id=OuterRef("item_id"),
        )
        .order_by("-date")
        .values("date")[:1]
    )
    history_rows = EveMarketItemHistory.objects.filter(
        region_id=region_id,
        item_id__in=unique_ids,
        date=Subquery(latest_date),
    ).values_list("item_id", "average")
    for type_id, average in history_rows:
        if average is not None:
            prices[int(type_id)] = int(average)

    missing = [tid for tid in unique_ids if tid not in prices]
    if missing:
        for type_id, average in EveMarketPrice.objects.filter(
            eve_type_id__in=missing
        ).values_list("eve_type_id", "average_price"):
            if average is not None:
                prices[int(type_id)] = int(average)

    return prices


def get_volume_90d_by_type_id(type_ids: list[int]) -> dict[int, int]:
    """Return summed market history volume over the last 90 days by type ID."""
    if not type_ids:
        return {}

    unique_ids = list({int(tid) for tid in type_ids})
    region_id = _baseline_region_id()
    cutoff = timezone.now().date() - timedelta(days=VOLUME_LOOKBACK_DAYS)
    rows = (
        EveMarketItemHistory.objects.filter(
            region_id=region_id,
            item_id__in=unique_ids,
            date__gte=cutoff,
        )
        .values("item_id")
        .annotate(total=Sum("volume"))
    )
    return {
        int(row["item_id"]): int(row["total"] or 0)
        for row in rows
        if row["total"] is not None
    }
