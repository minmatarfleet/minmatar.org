"""Industry order assignment reports (committed vs delivered)."""

from collections import defaultdict
from decimal import Decimal

from datetime import datetime

from django.utils import timezone

from eveonline.models import EveCharacter
from eveonline.models.characters import EvePlayer
from industry.models import IndustryOrderItemAssignment
from tribes.reports.roster import roster_character_pks, roster_user_ids
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = [
    "primary_character",
    "committed_units",
    "delivered_units",
    "committed_estimate",
    "delivered_estimate",
    "committed_margin",
    "delivered_margin",
]


def run_industry_orders_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    char_pks = roster_character_pks(tribe_group)
    user_ids = roster_user_ids(tribe_group)
    if not char_pks:
        return [], _empty_totals(), COLUMNS

    period_start_dt = timezone.make_aware(
        datetime.combine(period.start, datetime.min.time())
    )
    period_end_dt = timezone.make_aware(
        datetime.combine(period.end, datetime.max.time())
    )

    assignments = IndustryOrderItemAssignment.objects.filter(
        character_id__in=char_pks,
        order_item__order__tribe_groups=tribe_group,
    ).select_related("order_item", "order_item__order", "character")

    committed: dict[int, dict] = defaultdict(_metric_dict)
    delivered: dict[int, dict] = defaultdict(_metric_dict)

    for a in assignments:
        uid = a.character.user_id if a.character else None
        if not uid:
            continue
        order = a.order_item.order
        unit_price = _dec(
            a.target_unit_price or a.order_item.target_unit_price or 0
        )
        unit_margin = _dec(
            a.target_estimated_margin
            or a.order_item.target_estimated_margin
            or 0
        )
        qty = Decimal(a.quantity)

        if order.fulfilled_at is None:
            _add(committed[uid], qty, unit_price, unit_margin)

        fulfilled_at = a.delivered_at or order.fulfilled_at
        if fulfilled_at and period_start_dt <= fulfilled_at <= period_end_dt:
            _add(delivered[uid], qty, unit_price, unit_margin)

    rows = []
    for uid in user_ids:
        c = committed[uid]
        d = delivered[uid]
        rows.append(
            {
                "primary_character": _primary_name(uid),
                "committed_units": int(c["units"]),
                "delivered_units": int(d["units"]),
                "committed_estimate": float(c["estimate"]),
                "delivered_estimate": float(d["estimate"]),
                "committed_margin": float(c["margin"]),
                "delivered_margin": float(d["margin"]),
            }
        )
    rows.sort(key=lambda r: r["delivered_margin"], reverse=True)

    totals = {
        "committed_units": sum(r["committed_units"] for r in rows),
        "delivered_units": sum(r["delivered_units"] for r in rows),
        "delivered_margin": sum(r["delivered_margin"] for r in rows),
        "delivered_estimate": sum(r["delivered_estimate"] for r in rows),
    }
    return rows, totals, COLUMNS


def _metric_dict():
    return {"units": Decimal(0), "estimate": Decimal(0), "margin": Decimal(0)}


def _add(bucket, qty, unit_price, unit_margin):
    bucket["units"] += qty
    bucket["estimate"] += qty * unit_price
    bucket["margin"] += qty * unit_margin


def _dec(val):
    return Decimal(val or 0)


def _empty_totals():
    return {
        "committed_units": 0,
        "delivered_units": 0,
        "delivered_margin": 0.0,
        "delivered_estimate": 0.0,
    }


def _primary_name(user_id):
    player = (
        EvePlayer.objects.filter(user_id=user_id)
        .select_related("primary_character")
        .first()
    )
    if player and player.primary_character:
        return player.primary_character.character_name or ""
    c = EveCharacter.objects.filter(user_id=user_id).first()
    return c.character_name if c else ""
