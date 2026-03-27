"""Build the daily Discord message for industry order overview."""

from __future__ import annotations

from decimal import Decimal

from industry.endpoints.orders.serialization import order_line_list_targets
from industry.models import IndustryOrder

MAX_SECTION_LINES = 35
BILLION = Decimal("1000000000")


def _format_billions(isk: Decimal) -> str:
    if isk <= 0:
        return "0B"
    billions = isk / BILLION
    text = f"{billions:.2f}".rstrip("0").rstrip(".")
    return f"{text}B"


def _truncated_lines(lines: list[str], limit: int) -> list[str]:
    if len(lines) <= limit:
        return lines
    extra = len(lines) - limit
    return lines[:limit] + [f"- … and {extra} more"]


def build_industry_daily_summary_message() -> str:
    """
    Markdown-ish plain text for Discord: active orders, unfulfilled lines,
    totals from **undelivered** assignments on active orders (ISK → B).
    """
    active_orders = (
        IndustryOrder.objects.filter(fulfilled_at__isnull=True)
        .prefetch_related(
            "items__eve_type",
            "items__assignments__character",
        )
        .order_by("needed_by", "-created_at")
    )

    active_list: list[str] = []
    unfulfilled_list: list[str] = []
    total_order_isk = Decimal(0)
    total_margin_isk = Decimal(0)

    for order in active_orders:
        oid = order.order_identifier
        active_list.append(f"- `{oid}` (needed {order.needed_by.isoformat()})")

        for item in order.items.all():
            assignments = list(item.assignments.all())
            assigned_qty = sum(a.quantity for a in assignments)
            unassigned = max(0, item.quantity - assigned_qty)
            undelivered_qty = sum(
                a.quantity for a in assignments if a.delivered_at is None
            )

            if unassigned == 0 and undelivered_qty == 0:
                continue

            type_name = item.eve_type.name
            if unassigned > 0:
                unfulfilled_list.append(
                    f"- `{oid}` - {type_name} x{unassigned}"
                )
            elif undelivered_qty > 0:
                unfulfilled_list.append(
                    f"- `{oid}` - {type_name} ({undelivered_qty} in progress)"
                )

            line_unit, line_margin = order_line_list_targets(item)
            for a in assignments:
                if a.delivered_at is not None:
                    continue
                unit = a.target_unit_price or line_unit
                margin = a.target_estimated_margin or line_margin
                q = Decimal(a.quantity)
                if unit is not None:
                    total_order_isk += q * unit
                if margin is not None:
                    total_margin_isk += q * margin

    if not active_list:
        active_lines = ["- *(none)*"]
    else:
        active_lines = _truncated_lines(active_list, MAX_SECTION_LINES)

    if not unfulfilled_list:
        unfulfilled_lines = ["- *(none)*"]
    else:
        unfulfilled_lines = _truncated_lines(
            unfulfilled_list, MAX_SECTION_LINES
        )

    lines = [
        "# Industry order summary",
        "",
        "## Active orders",
        *active_lines,
        "",
        "## Unfulfilled order items",
        *unfulfilled_lines,
        "",
        f"**Total order amount:** {_format_billions(total_order_isk)}",
        f"**Total available margin:** {_format_billions(total_margin_isk)}",
    ]
    return "\n".join(lines)
