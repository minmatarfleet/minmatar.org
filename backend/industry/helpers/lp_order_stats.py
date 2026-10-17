"""Rolling LP buyback order stats for the public buyback page."""

from __future__ import annotations

from datetime import date, timedelta
from statistics import median

from django.db.models import Min, Q
from django.utils import timezone

from eveonline.models import EvePlayer
from industry.helpers.lp_market_orders import CANCELLED, COMPLETED, EXPRESS
from industry.models import (
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
)

DEFAULT_STATS_DAYS = 30
# Weeks of completed LP shown in the buyback page's weekly bars.
WEEKLY_WEEKS = 12
DAY_SECONDS = 24 * 3600


def _median_seconds(values: list[float]) -> int | None:
    return round(median(values)) if values else None


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
        "median_close_seconds": _median_seconds(close_seconds),
        "paid_within_day": sum(1 for s in close_seconds if s <= DAY_SECONDS),
        "lp_completed": lp_total,
        "isk_completed": isk_total,
        "avg_isk_per_lp": (
            round(isk_total / lp_total, 1) if lp_total > 0 else None
        ),
    }


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _weekly(qs, now) -> list[dict]:
    """LP completed per Monday-start week, oldest first, current week last."""
    this_week = _week_start(now.date())
    first_week = this_week - timedelta(weeks=WEEKLY_WEEKS - 1)
    totals = {first_week + timedelta(weeks=i): 0 for i in range(WEEKLY_WEEKS)}
    rows = qs.filter(
        status=COMPLETED, completed_at__date__gte=first_week
    ).values_list("completed_at", "quantity")
    for completed_at, quantity in rows:
        week = _week_start(completed_at.date())
        if week in totals:
            totals[week] += quantity
    return [{"week_start": week, "lp": lp} for week, lp in totals.items()]


def _converters(completed_ids: list[int]) -> list[dict]:
    """Who paid sellers in the window: claims on completed orders."""
    claims = (
        IndustryLoyaltyPointMarketOrderClaim.objects.filter(
            order_id__in=completed_ids, claimed_by__isnull=False
        )
        .select_related("claimed_by", "order")
        .order_by("created_at")
    )
    by_user: dict[int, dict] = {}
    for claim in claims:
        order = claim.order
        row = by_user.setdefault(
            claim.claimed_by_id,
            {
                "user": claim.claimed_by,
                "orders": set(),
                "lp": 0,
                "isk": 0,
                "settle": [],
            },
        )
        row["orders"].add(order.pk)
        row["lp"] += int(claim.amount)
        row["isk"] += int(claim.amount) * order.isk_per_lp
        if order.completed_at:
            row["settle"].append(
                (order.completed_at - claim.created_at).total_seconds()
            )

    primaries = {
        player.user_id: player.primary_character
        for player in EvePlayer.objects.filter(
            user_id__in=by_user
        ).select_related("primary_character")
    }
    converters = []
    for user_id, row in by_user.items():
        user = row["user"]
        primary = primaries.get(user_id)
        converters.append(
            {
                "user_id": user_id,
                "name": primary.character_name if primary else user.username,
                "character_id": (
                    int(primary.character_id) if primary else None
                ),
                "orders": len(row["orders"]),
                "lp": row["lp"],
                "isk": row["isk"],
                "median_settle_seconds": _median_seconds(row["settle"]),
            }
        )
    converters.sort(key=lambda c: (-c["lp"], c["name"]))
    return converters


def order_stats(
    *, loyalty_point_id: int | None = None, days: int = DEFAULT_STATS_DAYS
) -> dict:
    """
    Order count, close time, ISK/LP and who paid over the last ``days``.

    ``orders`` counts non-cancelled orders posted in the window. Close time
    and ISK/LP (LP-weighted) cover orders completed in the window, so
    cancelled orders never count against the SLA. The wait splits at the
    first claim: posted -> claimed, then claimed -> paid. ``weekly`` always
    spans the last 12 weeks. Small table (a few hundred rows): inline.
    """
    now = timezone.now()
    since = now - timedelta(days=days)
    qs = IndustryLoyaltyPointMarketOrder.objects.exclude(status=CANCELLED)
    if loyalty_point_id is not None:
        qs = qs.filter(loyalty_point_id=loyalty_point_id)
    rows = list(
        qs.filter(
            Q(created_at__gte=since)
            | Q(status=COMPLETED, completed_at__gte=since)
        )
        .annotate(first_claim_at=Min("claims__created_at"))
        .values(
            "id",
            "tier",
            "status",
            "quantity",
            "isk_per_lp",
            "created_at",
            "completed_at",
            "first_claim_at",
        )
    )

    def is_completed(row: dict) -> bool:
        return (
            row["status"] == COMPLETED
            and row["completed_at"] is not None
            and row["completed_at"] >= since
        )

    def split(tier_rows: list[dict]) -> dict:
        posted = [r for r in tier_rows if r["created_at"] >= since]
        return _summary(posted, [r for r in tier_rows if is_completed(r)])

    completed = [r for r in rows if is_completed(r)]
    claimed = [r for r in completed if r["first_claim_at"] is not None]
    express = [r for r in rows if r["tier"] == EXPRESS]
    standard = [r for r in rows if r["tier"] != EXPRESS]
    return {
        "days": days,
        **split(rows),
        "median_claim_seconds": _median_seconds(
            [
                (r["first_claim_at"] - r["created_at"]).total_seconds()
                for r in claimed
            ]
        ),
        "median_settle_seconds": _median_seconds(
            [
                (r["completed_at"] - r["first_claim_at"]).total_seconds()
                for r in claimed
            ]
        ),
        "standard": split(standard),
        "express": split(express),
        "weekly": _weekly(qs, now),
        "converters": _converters([r["id"] for r in completed]),
    }
