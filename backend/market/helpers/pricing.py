"""Market price helpers for implant and item valuation."""

from django.db.models import OuterRef, Subquery

from eveonline.models import EveLocation
from eveuniverse.models import EveMarketPrice
from market.models.history import EveMarketItemHistory

JITA_REGION_ID = 10000002


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

    baseline = EveLocation.objects.filter(price_baseline=True).first()
    region_id = (
        baseline.region_id
        if baseline and baseline.region_id
        else JITA_REGION_ID
    )

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
