"""Infer structure-market sell volume from successive order-book snapshots."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Iterable, Sequence

from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from market.helpers.pricing import get_prices_by_type_id
from market.models import EveMarketInferredSale

GAP_MAX_AGE = timedelta(minutes=30)
BASELINE_PRICE_MULTIPLIER = 10
PRUNE_RETENTION = timedelta(days=90)
REASON_PARTIAL_FILL = EveMarketInferredSale.REASON_PARTIAL_FILL
REASON_SELLOUT = EveMarketInferredSale.REASON_SELLOUT


@dataclass(frozen=True)
class SnapshotOrder:
    order_id: int
    type_id: int
    price: Decimal
    volume_remain: int
    is_buy_order: bool
    issued: datetime | None = None
    duration_days: int | None = None


@dataclass(frozen=True)
class InferredSaleDraft:
    type_id: int
    quantity: int
    price: Decimal
    order_id: int | None
    reason: str


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.utc)
    return dt


def parse_esi_order(raw: dict) -> SnapshotOrder | None:
    """Parse one ESI structure-market order dict into a SnapshotOrder."""
    order_id = raw.get("order_id")
    type_id = raw.get("type_id")
    if order_id is None or type_id is None:
        return None

    issued_raw = raw.get("issued")
    issued: datetime | None = None
    if isinstance(issued_raw, datetime):
        issued = _ensure_aware(issued_raw)
    elif isinstance(issued_raw, str):
        issued = _ensure_aware(parse_datetime(issued_raw))

    duration = raw.get("duration")
    duration_days = int(duration) if duration is not None else None

    volume = raw.get("volume_remain", raw.get("volume_total", 0))
    return SnapshotOrder(
        order_id=int(order_id),
        type_id=int(type_id),
        price=Decimal(str(raw["price"])),
        volume_remain=int(volume or 0),
        is_buy_order=bool(raw.get("is_buy_order", False)),
        issued=issued,
        duration_days=duration_days,
    )


def orders_from_db_rows(rows: Iterable) -> list[SnapshotOrder]:
    """Build SnapshotOrder list from EveMarketItemOrder queryset/rows."""
    orders: list[SnapshotOrder] = []
    for row in rows:
        if row.order_id is None:
            continue
        orders.append(
            SnapshotOrder(
                order_id=int(row.order_id),
                type_id=int(row.item_id),
                price=Decimal(row.price),
                volume_remain=int(row.quantity),
                is_buy_order=bool(row.is_buy_order),
                issued=_ensure_aware(row.issued),
                duration_days=row.duration_days,
            )
        )
    return orders


def _min_sell_by_type(orders: Sequence[SnapshotOrder]) -> dict[int, Decimal]:
    mins: dict[int, Decimal] = {}
    for order in orders:
        if order.is_buy_order:
            continue
        current = mins.get(order.type_id)
        if current is None or order.price < current:
            mins[order.type_id] = order.price
    return mins


def _is_expired(order: SnapshotOrder, now: datetime) -> bool:
    if order.issued is None or order.duration_days is None:
        return False
    expires_at = order.issued + timedelta(days=int(order.duration_days))
    return expires_at <= now


def infer_sales_from_snapshots(
    previous: Sequence[SnapshotOrder],
    current: Sequence[SnapshotOrder],
    previous_synced_at: datetime | None,
    now: datetime,
    baseline_by_type: dict[int, int | float | Decimal] | None = None,
) -> list[InferredSaleDraft]:
    """
    Infer sell fills between two sell-order snapshots.

    Guards (in order): gap >30m → []; partial fills; vanished with
    expiry / competitive / 10× baseline checks → sellout.
    """
    now = _ensure_aware(now) or timezone.now()
    previous_synced_at = _ensure_aware(previous_synced_at)

    if previous_synced_at is None or (now - previous_synced_at) > GAP_MAX_AGE:
        return []

    prev_sells = [o for o in previous if not o.is_buy_order]
    curr_sells = [o for o in current if not o.is_buy_order]
    prev_by_id = {o.order_id: o for o in prev_sells}
    curr_by_id = {o.order_id: o for o in curr_sells}
    min_sell = _min_sell_by_type(prev_sells)

    type_ids = {o.type_id for o in prev_sells}
    if baseline_by_type is None:
        baselines = get_prices_by_type_id(list(type_ids)) if type_ids else {}
    else:
        baselines = baseline_by_type

    drafts: list[InferredSaleDraft] = []

    for order_id, prev in prev_by_id.items():
        curr = curr_by_id.get(order_id)
        if curr is not None:
            if curr.volume_remain < prev.volume_remain:
                delta = prev.volume_remain - curr.volume_remain
                if delta > 0:
                    drafts.append(
                        InferredSaleDraft(
                            type_id=prev.type_id,
                            quantity=delta,
                            price=prev.price,
                            order_id=order_id,
                            reason=REASON_PARTIAL_FILL,
                        )
                    )
            continue

        # Vanished
        if _is_expired(prev, now):
            continue
        type_min = min_sell.get(prev.type_id)
        if type_min is not None and prev.price > type_min:
            continue
        baseline = baselines.get(prev.type_id) or 0
        if baseline > 0 and prev.price > (
            Decimal(str(baseline)) * BASELINE_PRICE_MULTIPLIER
        ):
            continue
        if prev.volume_remain <= 0:
            continue
        drafts.append(
            InferredSaleDraft(
                type_id=prev.type_id,
                quantity=prev.volume_remain,
                price=prev.price,
                order_id=order_id,
                reason=REASON_SELLOUT,
            )
        )

    return drafts


def daily_volume_buckets(
    location_id: int,
    *,
    days: int = 30,
    type_id: int | None = None,
    end: date | None = None,
) -> list[dict]:
    """
    Zero-filled day buckets of inferred units for a location.

    Returns [{date: ISO date, units: int}, ...] oldest → newest.
    """
    days = max(1, int(days))
    end_date = end or timezone.localdate()
    start_date = end_date - timedelta(days=days - 1)

    qs = EveMarketInferredSale.objects.filter(
        location_id=location_id,
        inferred_at__date__gte=start_date,
        inferred_at__date__lte=end_date,
    )
    if type_id is not None:
        qs = qs.filter(item_id=type_id)

    by_day: dict[date, int] = defaultdict(int)
    for row in (
        qs.values("inferred_at__date")
        .annotate(units=Sum("quantity"))
        .order_by("inferred_at__date")
    ):
        by_day[row["inferred_at__date"]] = int(row["units"] or 0)

    buckets: list[dict] = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        buckets.append({"date": day.isoformat(), "units": by_day.get(day, 0)})
    return buckets


def _days_of_data(location_id: int, end_date: date) -> int:
    earliest = (
        EveMarketInferredSale.objects.filter(location_id=location_id)
        .order_by("inferred_at")
        .values_list("inferred_at", flat=True)
        .first()
    )
    if earliest is None:
        return 0
    earliest_date = timezone.localtime(earliest).date()
    return max(1, (end_date - earliest_date).days + 1)


def velocity_stats(
    buckets: Sequence[dict],
    *,
    long_days: int = 30,
    short_days: int = 7,
    days_of_data: int | None = None,
) -> dict:
    """
    Velocity from zero-filled daily buckets.

    - long window median of daily units (effective days clamped)
    - short window mean with per-day cap at 4× median when median > 0
    """
    units = [int(b.get("units") or 0) for b in buckets]
    n = len(units)
    if days_of_data is None:
        days_of_data = n
    effective_long = max(0, min(long_days, days_of_data, n))
    effective_short = max(0, min(short_days, days_of_data, n))

    long_window = units[-effective_long:] if effective_long else []
    short_window = units[-effective_short:] if effective_short else []

    long_median = float(median(long_window)) if long_window else 0.0
    if long_median > 0:
        cap = 4.0 * long_median
        capped = [min(float(u), cap) for u in short_window]
    else:
        capped = [float(u) for u in short_window]
    short_mean = (sum(capped) / len(capped)) if capped else 0.0

    return {
        "long_days": effective_long,
        "short_days": effective_short,
        "days_of_data": days_of_data,
        "median_daily_units": long_median,
        "short_mean_daily_units": short_mean,
        "total_units": sum(units),
    }


def prune_inferred_sales(
    *,
    older_than: timedelta = PRUNE_RETENTION,
    now: datetime | None = None,
) -> int:
    """Delete inferred sales older than retention window. Returns count deleted."""
    cutoff = (now or timezone.now()) - older_than
    deleted, _ = EveMarketInferredSale.objects.filter(
        inferred_at__lt=cutoff
    ).delete()
    return deleted


def top_movers(
    location_id: int,
    *,
    days: int = 7,
    limit: int = 10,
    end: date | None = None,
) -> list[dict]:
    """Top types by inferred units over the window."""
    days = max(1, int(days))
    end_date = end or timezone.localdate()
    start_date = end_date - timedelta(days=days - 1)

    rows = (
        EveMarketInferredSale.objects.filter(
            location_id=location_id,
            inferred_at__date__gte=start_date,
            inferred_at__date__lte=end_date,
        )
        .values("item_id", "item__name")
        .annotate(units=Sum("quantity"))
        .order_by("-units")[:limit]
    )
    return [
        {
            "type_id": int(row["item_id"]),
            "item_name": row["item__name"] or str(row["item_id"]),
            "units": int(row["units"] or 0),
        }
        for row in rows
    ]


def build_volume_response(
    location_id: int,
    *,
    days: int = 7,
    type_id: int | None = None,
) -> dict:
    """Assemble API payload for inferred sales volume."""
    days = max(1, min(int(days), 90))
    end_date = timezone.localdate()
    buckets = daily_volume_buckets(
        location_id, days=days, type_id=type_id, end=end_date
    )
    # Velocity always uses up to 30d of history (clamped by days_of_data).
    velocity_buckets = (
        buckets
        if days >= 30
        else daily_volume_buckets(
            location_id, days=30, type_id=type_id, end=end_date
        )
    )
    data_days = _days_of_data(location_id, end_date)
    velocity = velocity_stats(
        velocity_buckets,
        long_days=30,
        short_days=7,
        days_of_data=data_days if data_days else 0,
    )
    # total_units reflects the requested display window, not the 30d velocity lookback.
    velocity["total_units"] = sum(int(b.get("units") or 0) for b in buckets)
    movers = (
        []
        if type_id is not None
        else top_movers(location_id, days=days, end=end_date)
    )
    return {
        "location_id": location_id,
        "days": days,
        "buckets": buckets,
        "velocity": velocity,
        "top_movers": movers,
    }
