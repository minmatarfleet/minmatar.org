"""
Per-order profit/price breakdown snapshots for graphs and order summaries.

Snapshots are written at order creation (best-effort) and can be refreshed
while the order is open, or once when no snapshot exists yet.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from django.utils import timezone

from industry.helpers.discord_summary_display import order_location_short_label
from industry.helpers.facility_api import FACILITY_SYSTEM_NAMES
from industry.helpers.orders_profit_summary import (
    OrdersProfitSummary,
    ProfitSummaryOrder,
    ProfitSummaryRow,
    ProfitSummaryTotals,
    _parse_order_ids,
    build_orders_profit_summary,
    filter_orders_queryset,
)
from industry.helpers.product_unit_cost import FACILITY_KEY
from industry.models import IndustryOrder

DEFAULT_FACILITY_KEY = FACILITY_KEY
DEFAULT_COMPRESSED = True


class ProfitBreakdownRefreshNotAllowed(Exception):
    """Raised when a fulfilled order already has a stored breakdown."""


def _row_to_dict(row: ProfitSummaryRow) -> Dict[str, Any]:
    return {
        "name": row.name,
        "type_id": row.type_id,
        "kind": row.kind,
        "qty": row.qty,
        "isk_per_lp": row.isk_per_lp,
        "cost_per": row.cost_per,
        "unit_price": row.unit_price,
        "price_source": row.price_source,
        "profit_per": row.profit_per,
        "order_profit": row.order_profit,
        "note": row.note,
    }


def _totals_to_dict(totals: ProfitSummaryTotals) -> Dict[str, Any]:
    return {
        "total_order_amount": totals.total_order_amount,
        "total_profit": totals.total_profit,
        "line_count": totals.line_count,
        "total_qty": totals.total_qty,
        "best_name": totals.best_name,
        "best_profit": totals.best_profit,
        "worst_name": totals.worst_name,
        "worst_profit": totals.worst_profit,
    }


def _payload_from_summary(summary: OrdersProfitSummary) -> Dict[str, Any]:
    return {
        "rows": [_row_to_dict(r) for r in summary.rows],
        "totals": _totals_to_dict(summary.totals),
        "assumptions": list(summary.assumptions),
        "facility_key": summary.facility_key,
        "compressed": summary.compressed,
    }


def compute_order_profit_breakdown(
    order: IndustryOrder,
    *,
    facility_key: str = DEFAULT_FACILITY_KEY,
    compressed: bool = DEFAULT_COMPRESSED,
) -> Dict[str, Any]:
    """Live-plan this order and return a storable breakdown payload."""
    summary = build_orders_profit_summary(
        open_only=False,
        order_ids=[order.pk],
        facility_key=facility_key,
        compressed=compressed,
    )
    return _payload_from_summary(summary)


def store_order_profit_breakdown(
    order: IndustryOrder, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Persist payload on the order and return it."""
    order.profit_breakdown = payload
    order.profit_breakdown_computed_at = timezone.now()
    order.save(
        update_fields=["profit_breakdown", "profit_breakdown_computed_at"]
    )
    return payload


def get_order_profit_breakdown(
    order: IndustryOrder,
) -> Optional[Dict[str, Any]]:
    """Return the stored breakdown, or None if none has been computed yet."""
    if order.profit_breakdown:
        return order.profit_breakdown
    return None


def ensure_order_profit_breakdown(order: IndustryOrder) -> Dict[str, Any]:
    """Return stored breakdown, computing and storing it if missing."""
    existing = get_order_profit_breakdown(order)
    if existing is not None:
        return existing
    payload = compute_order_profit_breakdown(order)
    return store_order_profit_breakdown(order, payload)


def can_refresh_order_profit_breakdown(order: IndustryOrder) -> bool:
    """True when refresh is allowed (open, or no snapshot yet)."""
    return order.fulfilled_at is None or order.profit_breakdown is None


def refresh_order_profit_breakdown(order: IndustryOrder) -> Dict[str, Any]:
    """
    Recompute and overwrite the stored breakdown.

    Allowed when the order is still open, or when no breakdown exists yet.
    """
    if not can_refresh_order_profit_breakdown(order):
        raise ProfitBreakdownRefreshNotAllowed(
            "Cannot refresh profit breakdown for a fulfilled order that "
            "already has a stored snapshot."
        )
    payload = compute_order_profit_breakdown(order)
    return store_order_profit_breakdown(order, payload)


def _merge_price_source(existing: Optional[str], incoming: str) -> str:
    if existing is None:
        return incoming
    if existing == incoming:
        return existing
    return "mixed"


def _row_from_dict(data: Dict[str, Any]) -> ProfitSummaryRow:
    return ProfitSummaryRow(
        name=str(data.get("name") or ""),
        type_id=int(data["type_id"]),
        kind=str(data.get("kind") or "T1"),
        qty=int(data.get("qty") or 0),
        isk_per_lp=(
            float(data["isk_per_lp"])
            if data.get("isk_per_lp") is not None
            else None
        ),
        cost_per=int(data.get("cost_per") or 0),
        unit_price=int(data.get("unit_price") or 0),
        price_source=str(data.get("price_source") or "jita"),
        profit_per=int(data.get("profit_per") or 0),
        order_profit=int(data.get("order_profit") or 0),
        note=data.get("note"),
    )


def _aggregate_rows_from_payloads(
    payloads: Sequence[Dict[str, Any]],
) -> List[ProfitSummaryRow]:
    """Merge per-order snapshot rows by type_id."""
    qty_by_type: Dict[int, int] = {}
    revenue_by_type: Dict[int, int] = {}
    cost_by_type: Dict[int, int] = {}
    profit_by_type: Dict[int, int] = {}
    name_by_type: Dict[int, str] = {}
    kind_by_type: Dict[int, str] = {}
    isk_per_lp_by_type: Dict[int, Optional[float]] = {}
    price_source_by_type: Dict[int, str] = {}
    notes_by_type: Dict[int, List[str]] = {}

    for payload in payloads:
        for raw in payload.get("rows") or []:
            row = _row_from_dict(raw)
            tid = row.type_id
            qty_by_type[tid] = qty_by_type.get(tid, 0) + row.qty
            revenue_by_type[tid] = revenue_by_type.get(tid, 0) + (
                row.unit_price * row.qty
            )
            cost_by_type[tid] = cost_by_type.get(tid, 0) + (
                row.cost_per * row.qty
            )
            profit_by_type[tid] = profit_by_type.get(tid, 0) + row.order_profit
            name_by_type[tid] = row.name or name_by_type.get(tid, str(tid))
            kind_by_type[tid] = row.kind or kind_by_type.get(tid, "T1")
            if tid not in isk_per_lp_by_type:
                isk_per_lp_by_type[tid] = row.isk_per_lp
            price_source_by_type[tid] = _merge_price_source(
                price_source_by_type.get(tid), row.price_source
            )
            if row.note:
                notes_by_type.setdefault(tid, []).append(row.note)

    rows: List[ProfitSummaryRow] = []
    for tid in sorted(qty_by_type.keys()):
        qty = qty_by_type[tid]
        unit_price = int(round(revenue_by_type[tid] / qty)) if qty else 0
        cost_per = int(round(cost_by_type[tid] / qty)) if qty else 0
        order_profit = profit_by_type[tid]
        profit_per = int(round(order_profit / qty)) if qty else 0
        notes = notes_by_type.get(tid) or []
        note = "; ".join(dict.fromkeys(notes)) if notes else None
        rows.append(
            ProfitSummaryRow(
                name=name_by_type[tid],
                type_id=tid,
                kind=kind_by_type[tid],
                qty=qty,
                isk_per_lp=isk_per_lp_by_type.get(tid),
                cost_per=cost_per,
                unit_price=unit_price,
                price_source=price_source_by_type[tid],
                profit_per=profit_per,
                order_profit=order_profit,
                note=note,
            )
        )
    rows.sort(key=lambda r: -r.order_profit)
    return rows


def _totals_from_rows(rows: List[ProfitSummaryRow]) -> ProfitSummaryTotals:
    if not rows:
        return ProfitSummaryTotals(
            total_order_amount=0,
            total_profit=0,
            line_count=0,
            total_qty=0,
            best_name=None,
            best_profit=None,
            worst_name=None,
            worst_profit=None,
        )
    best = rows[0]
    worst = rows[-1]
    return ProfitSummaryTotals(
        total_order_amount=sum(r.unit_price * r.qty for r in rows),
        total_profit=sum(r.order_profit for r in rows),
        line_count=len(rows),
        total_qty=sum(r.qty for r in rows),
        best_name=best.name,
        best_profit=best.order_profit,
        worst_name=worst.name,
        worst_profit=worst.order_profit,
    )


def compose_orders_profit_summary_from_snapshots(
    *,
    needed_by_from: Optional[date] = None,
    needed_by_to: Optional[date] = None,
    open_only: bool = True,
    order_ids: Optional[str | Sequence[int]] = None,
) -> OrdersProfitSummary:
    """
    Build an OrdersProfitSummary from stored per-order snapshots.

    Missing snapshots are skipped (no live planner on read). Use admin
    refresh or create-time ensure to populate them.
    """
    included_ids = _parse_order_ids(order_ids)
    candidates = list(
        filter_orders_queryset(
            needed_by_from=needed_by_from,
            needed_by_to=needed_by_to,
            open_only=open_only,
        ).prefetch_related("items")
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

    payloads: List[Dict[str, Any]] = []
    assumptions: List[str] = []
    facility_key = DEFAULT_FACILITY_KEY
    compressed = DEFAULT_COMPRESSED
    missing = 0
    for order in selected:
        payload = get_order_profit_breakdown(order)
        if payload is None:
            missing += 1
            continue
        payloads.append(payload)
        if not assumptions and payload.get("assumptions"):
            assumptions = list(payload["assumptions"])
        facility_key = str(payload.get("facility_key") or facility_key)
        compressed = bool(payload.get("compressed", compressed))

    rows = _aggregate_rows_from_payloads(payloads)
    totals = _totals_from_rows(rows)

    if not assumptions:
        system_name = FACILITY_SYSTEM_NAMES.get(
            facility_key, facility_key.title()
        )
        shopping = (
            f"Build costs use compressed ore shopping at {system_name}."
            if compressed
            else (
                f"Build costs use mineral shopping at {system_name} "
                "(not compressed ore)."
            )
        )
        assumptions = [
            shopping,
            (
                "Navy blueprint copies are ME 0 / TE 0 from the faction "
                "warfare LP store, priced with the alliance default ISK "
                "per LP rates."
            ),
            (
                "Tech 1 ships assume a researched ME 10 / TE 20 blueprint "
                "(no LP cost)."
            ),
            (
                "Each product's build cost is planned at its maximum claim "
                "size so ore buying matches how industrialists claim work."
            ),
            (
                "Revenue uses the order ask price when set; otherwise "
                "Jita sell."
            ),
            (
                "Quantities from included orders are added together for "
                "each product."
            ),
            (
                "Figures come from each order's stored profit breakdown "
                "snapshot."
            ),
        ]
    elif "stored profit breakdown" not in " ".join(assumptions).lower():
        assumptions = list(assumptions) + [
            (
                "Figures come from each order's stored profit breakdown "
                "snapshot."
            ),
        ]

    if missing:
        assumptions = list(assumptions) + [
            (
                f"{missing} included order(s) have no stored profit "
                "breakdown yet — refresh from the industry order admin "
                "to include them."
            ),
        ]

    return OrdersProfitSummary(
        orders=order_summaries,
        rows=rows,
        totals=totals,
        assumptions=assumptions,
        facility_key=facility_key,
        compressed=compressed,
    )
