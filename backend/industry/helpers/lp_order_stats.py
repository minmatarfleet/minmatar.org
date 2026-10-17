"""Rolling LP buyback order stats for the public buyback page."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from industry.helpers.lp_market_orders import CANCELLED, COMPLETED, EXPRESS
from industry.models import IndustryLoyaltyPointMarketOrder

DEFAULT_STATS_DAYS = 30


def _summary(posted: list[dict], completed: list[dict]) -> dict:
    close_seconds = [
        (row["completed_at"] - row["created_at"]).total_seconds()
        for row in completed
    ]
    lp_total = sum(row["quantity"] for row in completed)
    isk_total = sum(row["quantity"] * row["isk_per_lp"] for row in completed)
    return {
        "orders": len(posted),
        "completed": len(completed),
        "avg_close_seconds": (
            round(sum(close_seconds) / len(close_seconds))
            if close_seconds
            else None
        ),
        "avg_isk_per_lp": (
            round(isk_total / lp_total, 1) if lp_total > 0 else None
        ),
    }


def order_stats(
    *, loyalty_point_id: int | None = None, days: int = DEFAULT_STATS_DAYS
) -> dict:
    """
    Order count, close time and ISK/LP over the last ``days``.

    ``orders`` counts non-cancelled orders posted in the window. Close time
    and ISK/LP (LP-weighted) cover orders completed in the window, so
    cancelled orders never count against the SLA. Small table: one query.
    """
    since = timezone.now() - timedelta(days=days)
    qs = IndustryLoyaltyPointMarketOrder.objects.exclude(status=CANCELLED)
    if loyalty_point_id is not None:
        qs = qs.filter(loyalty_point_id=loyalty_point_id)
    rows = list(
        qs.filter(
            Q(created_at__gte=since)
            | Q(status=COMPLETED, completed_at__gte=since)
        ).values(
            "tier",
            "status",
            "quantity",
            "isk_per_lp",
            "created_at",
            "completed_at",
        )
    )

    def split(tier_rows: list[dict]) -> dict:
        posted = [r for r in tier_rows if r["created_at"] >= since]
        completed = [
            r
            for r in tier_rows
            if r["status"] == COMPLETED
            and r["completed_at"] is not None
            and r["completed_at"] >= since
        ]
        return _summary(posted, completed)

    express = [r for r in rows if r["tier"] == EXPRESS]
    standard = [r for r in rows if r["tier"] != EXPRESS]
    return {
        "days": days,
        **split(rows),
        "standard": split(standard),
        "express": split(express),
    }
