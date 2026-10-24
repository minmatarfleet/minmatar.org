"""LP the buyback program bought from pilots (Loyalty Points tribe)."""

from __future__ import annotations

from django.utils import timezone

from industry.helpers.lp_market_orders import COMPLETED
from industry.helpers.lp_order_stats import DAY_SECONDS, _converters, _weekly
from industry.models import IndustryLoyaltyPointMarketOrder
from tribes.reports.queries.common import (
    best_month,
    best_month_since,
    period_window,
)
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = [
    "primary_character_name",
    "lp",
    "isk",
    "orders",
    "median_settle_seconds",
]


def _completed_sells():
    """Pilots selling LP to the program; buy orders are the stockpile side."""
    return IndustryLoyaltyPointMarketOrder.objects.filter(
        side=IndustryLoyaltyPointMarketOrder.Side.SELL,
        status=COMPLETED,
        completed_at__isnull=False,
    )


def run_lp_buyback_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    """Program-wide totals; contributors are whoever paid the sellers."""
    start, end = period_window(period)
    orders = list(
        _completed_sells()
        .filter(completed_at__gte=start, completed_at__lte=end)
        .values(
            "id",
            "quantity",
            "isk_per_lp",
            "created_at",
            "completed_at",
            "created_by_id",
        )
    )
    lp = sum(o["quantity"] for o in orders)
    isk = sum(o["quantity"] * o["isk_per_lp"] for o in orders)
    within_day = sum(
        1
        for o in orders
        if (o["completed_at"] - o["created_at"]).total_seconds() <= DAY_SECONDS
    )
    rows = [
        {
            "user_id": c["user_id"],
            "primary_character_id": c["character_id"],
            "primary_character_name": c["name"],
            "lp": c["lp"],
            "isk": c["isk"],
            "orders": c["orders"],
            "median_settle_seconds": c["median_settle_seconds"],
        }
        for c in _converters([o["id"] for o in orders])
    ]
    totals = {
        "completed": len(orders),
        "lp_completed": lp,
        "isk_completed": isk,
        "pilots_paid": len(
            {o["created_by_id"] for o in orders if o["created_by_id"]}
        ),
        "paid_within_day_pct": (
            round(100 * within_day / len(orders)) if orders else 0
        ),
    }
    return rows, totals, COLUMNS


def lp_buyback_highlights(tribe_group, period: PeriodBounds) -> dict:
    sells = _completed_sells()
    weekly = _weekly(sells, timezone.now())
    all_time = list(
        sells.values_list("quantity", "isk_per_lp", "created_by_id")
    )
    weeks: dict = {}
    for completed_at, quantity in sells.values_list(
        "completed_at", "quantity"
    ):
        week = completed_at.date().isocalendar()[:2]
        weeks[week] = weeks.get(week, 0) + quantity
    return {
        "weekly": [
            {"week_start": w["week_start"].isoformat(), "lp": w["lp"]}
            for w in weekly
        ],
        "record_week_lp": max(weeks.values()) if weeks else 0,
        "best_month": best_month(
            sells.filter(completed_at__gte=best_month_since()).values_list(
                "completed_at", "quantity"
            )
        ),
        "all_time": {
            "lp": sum(q for q, _, _ in all_time),
            "isk": sum(q * rate for q, rate, _ in all_time),
            "pilots": len({uid for _, _, uid in all_time if uid}),
        },
    }
