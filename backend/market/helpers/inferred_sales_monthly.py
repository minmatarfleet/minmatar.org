"""Calendar-month inferred-sales aggregates for one market location.

Feeds the public Amamake Market Report extractor
(``frontend/app/scripts/amamake_market_extract.mjs``): totals, a per-day
series and a per-type breakdown for the month, all derived from the
append-only ``EveMarketInferredSale`` rows written by the order-book sync.
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.core.cache import cache
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from market.models import EveMarketInferredSale

# A closed month never changes; the running month gets a short TTL so the
# report can be previewed mid-month without hammering the table.
CACHE_TTL_CLOSED_MONTH = 60 * 60 * 24
CACHE_TTL_OPEN_MONTH = 60 * 15
CACHE_KEY = "market:inferred_sales_monthly:{location_id}:{year}-{month:02d}"

ISK_EXPR = ExpressionWrapper(
    F("quantity") * F("price"),
    output_field=DecimalField(max_digits=40, decimal_places=2),
)


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """UTC ``[start, end)`` for a calendar month."""
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    if not 2000 <= year <= 2200:
        raise ValueError("year out of range")
    start = datetime(year, month, 1, tzinfo=dt_timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=dt_timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=dt_timezone.utc)
    return start, end


def _isk(value) -> float:
    return float(value or 0)


def build_monthly_response(
    location_id: int,
    year: int,
    month: int,
    *,
    using: str | None = None,
) -> dict:
    """Assemble the monthly report payload (cached).

    Pass ``using`` to read from an alternate DB alias (e.g.
    ``production_readonly``). The public API leaves this unset.
    """
    start, end = month_bounds(year, month)
    key = CACHE_KEY.format(location_id=location_id, year=year, month=month)
    if using:
        key = f"{key}:using:{using}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    sales = EveMarketInferredSale.objects
    if using:
        sales = sales.using(using)
    qs = sales.filter(
        location_id=location_id,
        inferred_at__gte=start,
        inferred_at__lt=end,
    )

    totals = qs.aggregate(
        fills=Count("id"),
        units=Sum("quantity"),
        isk=Sum(ISK_EXPR),
    )

    days = [
        {
            "date": row["day"].isoformat(),
            "fills": int(row["fills"]),
            "units": int(row["units"] or 0),
            "isk": _isk(row["isk"]),
        }
        for row in (
            qs.annotate(day=TruncDate("inferred_at", tzinfo=dt_timezone.utc))
            .values("day")
            .annotate(
                fills=Count("id"), units=Sum("quantity"), isk=Sum(ISK_EXPR)
            )
            .order_by("day")
        )
    ]

    by_type = [
        {
            "type_id": int(row["item_id"]),
            "name": row["item__name"] or "",
            "group": row["item__eve_group__name"] or "",
            "category": row["item__eve_group__eve_category__name"] or "",
            "fills": int(row["fills"]),
            "units": int(row["units"] or 0),
            "isk": _isk(row["isk"]),
        }
        for row in (
            qs.values(
                "item_id",
                "item__name",
                "item__eve_group__name",
                "item__eve_group__eve_category__name",
            )
            .annotate(
                fills=Count("id"), units=Sum("quantity"), isk=Sum(ISK_EXPR)
            )
            .order_by("-isk", "item_id")
        )
    ]

    payload = {
        "location_id": location_id,
        "year": year,
        "month": month,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "totals": {
            "fills": int(totals["fills"] or 0),
            "units": int(totals["units"] or 0),
            "isk": _isk(totals["isk"]),
            "types": len(by_type),
        },
        "days": days,
        "by_type": by_type,
    }

    ttl = (
        CACHE_TTL_CLOSED_MONTH
        if end <= timezone.now()
        else CACHE_TTL_OPEN_MONTH
    )
    cache.set(key, payload, ttl)
    return payload
