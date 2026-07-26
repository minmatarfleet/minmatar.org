"""
Roll up open (or filtered) industry orders into canvas-style profit rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Set

from django.db.models import Prefetch, QuerySet

from industry.helpers.discord_summary_display import order_location_short_label
from industry.helpers.cost_breakdown import jita_sell_prices_by_type_id
from industry.helpers.facility_api import FACILITY_SYSTEM_NAMES
from industry.helpers.facility_profiles import FACILITY_PROFILES
from industry.helpers.product_unit_cost import (
    FACILITY_KEY,
    ProductUnitCost,
    plan_product_unit_cost,
)
from industry.models import IndustryOrder, IndustryOrderItem


@dataclass(frozen=True)
class ProfitSummaryOrder:
    id: int
    public_short_code: str
    needed_by: date
    location_label: str
    fulfilled_at: Optional[date]
    item_count: int
    item_type_ids: List[int]
    included: bool


@dataclass(frozen=True)
class ProfitSummaryRow:
    name: str
    type_id: int
    kind: str
    qty: int
    isk_per_lp: Optional[float]
    cost_per: int
    unit_price: int
    price_source: str  # "ask" | "jita" | "mixed"
    profit_per: int
    order_profit: int
    note: Optional[str] = None


@dataclass(frozen=True)
class ProfitSummaryTotals:
    total_order_amount: int
    total_profit: int
    line_count: int
    total_qty: int
    best_name: Optional[str]
    best_profit: Optional[int]
    worst_name: Optional[str]
    worst_profit: Optional[int]


@dataclass(frozen=True)
class OrdersProfitSummary:
    orders: List[ProfitSummaryOrder]
    rows: List[ProfitSummaryRow]
    totals: ProfitSummaryTotals
    assumptions: List[str]
    facility_key: str
    compressed: bool


def _parse_order_ids(raw: Optional[str | Sequence[int]]) -> Optional[Set[int]]:
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if not parts:
            return set()
        return {int(p) for p in parts}
    return {int(x) for x in raw}


def filter_orders_queryset(
    *,
    needed_by_from: Optional[date] = None,
    needed_by_to: Optional[date] = None,
    open_only: bool = True,
) -> QuerySet:
    qs = IndustryOrder.objects.all().select_related("location")
    if open_only:
        qs = qs.filter(fulfilled_at__isnull=True)
    if needed_by_from is not None:
        qs = qs.filter(needed_by__gte=needed_by_from)
    if needed_by_to is not None:
        qs = qs.filter(needed_by__lte=needed_by_to)
    return qs.order_by("needed_by", "pk")


def _line_ask_isk(item: IndustryOrderItem) -> Optional[int]:
    """Order-item ask, else first assignment ask (same precedence as list API)."""
    unit = item.target_unit_price
    if unit is None:
        for assignment in item.assignments.all():
            if assignment.target_unit_price is not None:
                unit = assignment.target_unit_price
                break
    if unit is None:
        return None
    return int(Decimal(unit))


def build_orders_profit_summary(  # noqa: C901
    *,
    needed_by_from: Optional[date] = None,
    needed_by_to: Optional[date] = None,
    open_only: bool = True,
    order_ids: Optional[str | Sequence[int]] = None,
    facility_key: str = FACILITY_KEY,
    compressed: bool = True,
) -> OrdersProfitSummary:
    key = (facility_key or FACILITY_KEY).lower().strip()
    if key not in FACILITY_PROFILES:
        raise ValueError(f"Unknown facility {facility_key!r}")

    included_ids = _parse_order_ids(order_ids)
    candidates = list(
        filter_orders_queryset(
            needed_by_from=needed_by_from,
            needed_by_to=needed_by_to,
            open_only=open_only,
        ).prefetch_related(
            Prefetch(
                "items",
                queryset=IndustryOrderItem.objects.select_related(
                    "eve_type"
                ).prefetch_related("assignments"),
            )
        )
    )

    order_summaries: List[ProfitSummaryOrder] = []
    selected: List[IndustryOrder] = []
    for order in candidates:
        items = list(order.items.all())
        item_type_ids = [int(item.eve_type_id) for item in items]
        included = included_ids is None or order.pk in included_ids
        fulfilled = (
            order.fulfilled_at.date()
            if order.fulfilled_at is not None
            else None
        )
        order_summaries.append(
            ProfitSummaryOrder(
                id=order.pk,
                public_short_code=order.public_short_code,
                needed_by=order.needed_by,
                location_label=order_location_short_label(order),
                fulfilled_at=fulfilled,
                item_count=len(items),
                item_type_ids=item_type_ids,
                included=included,
            )
        )
        if included:
            selected.append(order)

    qty_by_type: Dict[int, int] = {}
    name_by_type: Dict[int, str] = {}
    claim_qty_by_type: Dict[int, int] = {}
    ask_revenue_by_type: Dict[int, int] = {}
    ask_qty_by_type: Dict[int, int] = {}
    missing_ask_qty_by_type: Dict[int, int] = {}

    for order in selected:
        for item in order.items.all():
            tid = int(item.eve_type_id)
            qty = int(item.quantity)
            qty_by_type[tid] = qty_by_type.get(tid, 0) + qty
            name_by_type[tid] = item.eve_type.name
            claim = (
                int(item.self_assign_maximum)
                if item.self_assign_maximum is not None
                else qty
            )
            claim = max(claim, 1)
            claim_qty_by_type[tid] = max(claim_qty_by_type.get(tid, 0), claim)
            ask = _line_ask_isk(item)
            if ask is not None and ask > 0:
                ask_revenue_by_type[tid] = (
                    ask_revenue_by_type.get(tid, 0) + ask * qty
                )
                ask_qty_by_type[tid] = ask_qty_by_type.get(tid, 0) + qty
            else:
                missing_ask_qty_by_type[tid] = (
                    missing_ask_qty_by_type.get(tid, 0) + qty
                )

    type_ids = sorted(qty_by_type.keys())
    jita_prices = jita_sell_prices_by_type_id(type_ids) if type_ids else {}

    rows: List[ProfitSummaryRow] = []
    for tid in type_ids:
        qty = qty_by_type[tid]
        claim_qty = claim_qty_by_type.get(tid) or qty
        ask_qty = ask_qty_by_type.get(tid, 0)
        missing_qty = missing_ask_qty_by_type.get(tid, 0)
        jita = int(jita_prices.get(tid) or 0)
        revenue = ask_revenue_by_type.get(tid, 0) + jita * missing_qty
        unit_price = int(round(revenue / qty)) if qty else 0
        if ask_qty > 0 and missing_qty == 0:
            price_source = "ask"
        elif ask_qty == 0:
            price_source = "jita"
        else:
            price_source = "mixed"

        try:
            unit: ProductUnitCost = plan_product_unit_cost(
                tid,
                quantity=claim_qty,
                facility=key,
                compressed=compressed,
                use_production_lp=True,
                sell_prices=jita_prices,
            )
            cost_per = unit.cost_per
            kind = unit.kind
            isk_per_lp = unit.isk_per_lp
            name = unit.name or name_by_type.get(tid, str(tid))
            note = unit.note
        except Exception as exc:
            cost_per = 0
            kind = "T1"
            isk_per_lp = None
            name = name_by_type.get(tid, str(tid))
            note = f"Plan failed: {exc}"

        profit_per = unit_price - cost_per
        order_profit = profit_per * qty
        if price_source == "jita":
            extra = "Ask missing — used Jita sell"
            note = f"{note}; {extra}" if note else extra
        elif price_source == "mixed":
            extra = "Mixed ask + Jita sell"
            note = f"{note}; {extra}" if note else extra

        rows.append(
            ProfitSummaryRow(
                name=name,
                type_id=tid,
                kind=kind,
                qty=qty,
                isk_per_lp=isk_per_lp,
                cost_per=cost_per,
                unit_price=unit_price,
                price_source=price_source,
                profit_per=profit_per,
                order_profit=order_profit,
                note=note,
            )
        )

    rows.sort(key=lambda r: -r.order_profit)

    if rows:
        best = rows[0]
        worst = rows[-1]
        totals = ProfitSummaryTotals(
            total_order_amount=sum(r.unit_price * r.qty for r in rows),
            total_profit=sum(r.order_profit for r in rows),
            line_count=len(rows),
            total_qty=sum(r.qty for r in rows),
            best_name=best.name,
            best_profit=best.order_profit,
            worst_name=worst.name,
            worst_profit=worst.order_profit,
        )
    else:
        totals = ProfitSummaryTotals(
            total_order_amount=0,
            total_profit=0,
            line_count=0,
            total_qty=0,
            best_name=None,
            best_profit=None,
            worst_name=None,
            worst_profit=None,
        )

    system_name = FACILITY_SYSTEM_NAMES.get(key, key.title())
    if compressed:
        shopping = f"Build costs use compressed ore shopping at {system_name}."
    else:
        shopping = (
            f"Build costs use mineral shopping at {system_name} "
            "(not compressed ore)."
        )
    assumptions = [
        shopping,
        (
            "Navy blueprint copies are ME 0 / TE 0 from the faction warfare "
            "LP store, priced with the alliance default ISK per LP rates."
        ),
        (
            "Tech 1 ships assume a researched ME 10 / TE 20 blueprint "
            "(no LP cost)."
        ),
        (
            "Each product's build cost is planned at its maximum claim size "
            "so ore buying matches how industrialists claim work."
        ),
        ("Revenue uses the order ask price when set; otherwise Jita sell."),
        (
            "Quantities from included orders are added together for each "
            "product."
        ),
    ]

    return OrdersProfitSummary(
        orders=order_summaries,
        rows=rows,
        totals=totals,
        assumptions=assumptions,
        facility_key=key,
        compressed=compressed,
    )
