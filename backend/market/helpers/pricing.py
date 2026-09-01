"""
Jita / price_baseline **regional guide** prices.

Canonical source for “what is this worth in Jita?” is EveMarketItemHistory
for the price_baseline location’s region (The Forge when Jita is baseline),
with eveuniverse EveMarketPrice as fallback.

Do **not** use EveMarketItemLocationPrice (live station/structure order book,
aka “ItemPrice”) as the Jita guide — see docs/market-pricing.md and
.cursor/rules/market-pricing.mdc.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Sequence

from django.db.models import Max, Sum
from django.utils import timezone

from eveonline.models import EveLocation
from eveuniverse.models import EveMarketPrice
from market.models.history import EveMarketItemHistory

JITA_REGION_ID = 10000002
VOLUME_LOOKBACK_DAYS = 90
VOLUME_WINDOWS: tuple[int, ...] = (1, 7, 30)


def _baseline_region_id() -> int:
    region_id = (
        EveLocation.objects.filter(price_baseline=True)
        .values_list("region_id", flat=True)
        .first()
    )
    if region_id:
        return int(region_id)
    return JITA_REGION_ID


def get_history_averages_by_type_id(type_ids: list[int]) -> dict[int, Decimal]:
    """
    Latest EveMarketItemHistory.average (Decimal) for the price_baseline
    region, with EveMarketPrice.average_price fallback.

    MySQL-safe Max(date) per item + second filter (not correlated OuterRef).
    """
    if not type_ids:
        return {}

    unique_ids = list({int(tid) for tid in type_ids})
    prices: dict[int, Decimal] = {}
    region_id = _baseline_region_id()

    latest = dict(
        EveMarketItemHistory.objects.filter(
            region_id=region_id,
            item_id__in=unique_ids,
        )
        .values("item_id")
        .annotate(max_date=Max("date"))
        .values_list("item_id", "max_date")
    )
    if latest:
        for type_id, hist_date, average in EveMarketItemHistory.objects.filter(
            region_id=region_id,
            item_id__in=list(latest),
            date__in=set(latest.values()),
        ).values_list("item_id", "date", "average"):
            if latest.get(type_id) != hist_date or average is None:
                continue
            prices[int(type_id)] = Decimal(str(average))

    missing = [tid for tid in unique_ids if tid not in prices]
    if missing:
        for type_id, average in EveMarketPrice.objects.filter(
            eve_type_id__in=missing
        ).values_list("eve_type_id", "average_price"):
            if average is not None:
                prices[int(type_id)] = Decimal(str(average))

    return prices


def get_prices_by_type_id(type_ids: list[int]) -> dict[int, int]:
    """
    Return Jita-baseline ISK guide prices for type IDs.

    Prefers latest EveMarketItemHistory.average for the price_baseline
    location's region (Forge when Jita is baseline). Missing types fall
    back to EveMarketPrice.average_price.

    This is regional history, not EveMarketItemLocationPrice live orders.
    Integer ISK for most callers; use get_history_averages_by_type_id when
    fractional averages matter (e.g. buyback).
    """
    return {
        type_id: int(average)
        for type_id, average in get_history_averages_by_type_id(
            type_ids
        ).items()
    }


def get_volume_by_type_id(type_ids: list[int], *, days: int) -> dict[int, int]:
    """
    Sum EveMarketItemHistory.volume over the last ``days`` calendar days
    for the price_baseline region (Forge when Jita is baseline).
    """
    if not type_ids or days <= 0:
        return {}

    unique_ids = list({int(tid) for tid in type_ids})
    region_id = _baseline_region_id()
    cutoff = timezone.now().date() - timedelta(days=days)
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


def get_volume_90d_by_type_id(type_ids: list[int]) -> dict[int, int]:
    """Return summed market history volume over the last 90 days by type ID."""
    return get_volume_by_type_id(type_ids, days=VOLUME_LOOKBACK_DAYS)


def get_volume_weighted_average_by_type_id(
    type_ids: list[int], *, days: int = 7
) -> dict[int, int]:
    """
    Volume-weighted average of daily history ``average`` over the last
    ``days`` calendar days for the price_baseline region.

    Weighted as sum(average × volume) / sum(volume). When volume sums to
    zero but daily averages exist, falls back to a simple mean of those
    averages. Types with no history rows in the window are omitted.
    """
    if not type_ids or days <= 0:
        return {}

    unique_ids = list({int(tid) for tid in type_ids})
    region_id = _baseline_region_id()
    cutoff = timezone.now().date() - timedelta(days=days)

    by_type: Dict[int, List[tuple]] = {tid: [] for tid in unique_ids}
    for item_id, average, volume in EveMarketItemHistory.objects.filter(
        region_id=region_id,
        item_id__in=unique_ids,
        date__gte=cutoff,
    ).values_list("item_id", "average", "volume"):
        if average is None:
            continue
        by_type[int(item_id)].append((float(average), int(volume or 0)))

    out: dict[int, int] = {}
    for type_id, rows in by_type.items():
        if not rows:
            continue
        total_vol = sum(vol for _, vol in rows)
        if total_vol > 0:
            weighted = sum(avg * vol for avg, vol in rows)
            out[type_id] = int(round(weighted / total_vol))
        else:
            out[type_id] = int(round(sum(avg for avg, _ in rows) / len(rows)))
    return out


def get_volume_windows_by_type_id(
    type_ids: Iterable[int],
    windows: Sequence[int] = VOLUME_WINDOWS,
) -> Dict[int, Dict[int, Optional[int]]]:
    """
    Sum daily Forge/baseline history volume for each lookback window.

    One history query covering the widest window; per-type/per-window sums
    are computed in Python. Missing history → type omitted (callers treat
    as None / "—").
    """
    unique_ids = list({int(tid) for tid in type_ids})
    clean_windows = sorted({int(w) for w in windows if int(w) > 0})
    if not unique_ids or not clean_windows:
        return {}

    region_id = _baseline_region_id()
    today = timezone.now().date()
    max_days = clean_windows[-1]
    cutoff = today - timedelta(days=max_days)

    # {type_id: [(date, volume), ...]}
    by_type: Dict[int, List[tuple]] = {tid: [] for tid in unique_ids}
    for item_id, hist_date, volume in EveMarketItemHistory.objects.filter(
        region_id=region_id,
        item_id__in=unique_ids,
        date__gte=cutoff,
    ).values_list("item_id", "date", "volume"):
        by_type[int(item_id)].append((hist_date, int(volume or 0)))

    out: Dict[int, Dict[int, Optional[int]]] = {}
    for type_id, rows in by_type.items():
        if not rows:
            continue
        window_totals: Dict[int, Optional[int]] = {}
        for days in clean_windows:
            win_cutoff = today - timedelta(days=days)
            total = sum(vol for d, vol in rows if d >= win_cutoff)
            # Include zero when we saw rows in the outer window but none in
            # this shorter window (distinguish from completely missing).
            window_totals[days] = int(total)
        out[type_id] = window_totals
    return out
