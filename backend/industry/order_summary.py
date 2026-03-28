"""Query and format industry order data for Discord daily summary."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Case, IntegerField, Value, When

from industry.endpoints.orders.serialization import order_line_list_targets
from industry.helpers.discord_summary_display import (
    format_isk_billions_trimmed,
    format_margin_profit_parenthetical,
    order_location_short_label,
    pluralize_eve_group_name,
)
from industry.models import IndustryOrder
from industry.order_summary_types import (
    ActiveOrderSummaryLine,
    SummaryTotals,
    UnassignedOrderItemLine,
)


def get_active_order_display_items() -> list[ActiveOrderSummaryLine]:
    """Active orders, sorted by location (missing last), then pk."""
    qs = (
        IndustryOrder.objects.filter(fulfilled_at__isnull=True)
        .select_related("location")
        .prefetch_related("items__eve_type__eve_group")
        .annotate(
            loc_missing=Case(
                When(location_id__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    )
    orders = list(qs)

    def sort_key(o: IndustryOrder):
        label = order_location_short_label(o).lower()
        return (o.loc_missing, label, o.pk)

    orders.sort(key=sort_key)
    out: list[ActiveOrderSummaryLine] = []
    for order in orders:
        group_ids: dict[int, str] = {}
        for item in order.items.all():
            g = item.eve_type.eve_group
            if g is not None and g.id not in group_ids:
                group_ids[g.id] = pluralize_eve_group_name(g.name)
        names = sorted(group_ids.values(), key=str.lower)
        group_csv = ", ".join(names) if names else "—"
        profit = Decimal(0)
        for item in order.items.all():
            margin = order_line_list_targets(item)[1]
            if margin is not None:
                profit += Decimal(item.quantity) * margin
        out.append(
            ActiveOrderSummaryLine(
                public_short_code=order.public_short_code,
                location_label=order_location_short_label(order),
                group_names_csv=group_csv,
                profit_isk=profit,
            )
        )
    return out


def get_unassigned_order_items() -> list[UnassignedOrderItemLine]:
    """Positive unassigned lines across active orders; sort by location then pk, item id."""
    qs = (
        IndustryOrder.objects.filter(fulfilled_at__isnull=True)
        .select_related("location")
        .prefetch_related("items__eve_type")
    )
    orders = list(qs)

    def sort_key(o: IndustryOrder):
        missing = 1 if o.location_id is None else 0
        label = order_location_short_label(o).lower()
        return (missing, label, o.pk)

    orders.sort(key=sort_key)
    rows: list[UnassignedOrderItemLine] = []
    for order in orders:
        for item in order.items.all():
            assignments = list(item.assignments.all())
            assigned_qty = sum(a.quantity for a in assignments)
            unassigned = max(0, item.quantity - assigned_qty)
            if unassigned <= 0:
                continue
            margin = order_line_list_targets(item)[1]
            profit = (
                Decimal(0) if margin is None else Decimal(unassigned) * margin
            )
            rows.append(
                UnassignedOrderItemLine(
                    public_short_code=order.public_short_code,
                    location_label=order_location_short_label(order),
                    eve_type_name=item.eve_type.name,
                    unassigned_quantity=unassigned,
                    profit_isk=profit,
                )
            )
    return rows


def get_summary_totals_for_active_orders() -> SummaryTotals:
    """Roll up all assignment quantities × targets on active orders; ignore ``delivered_at``."""
    total_order_isk = Decimal(0)
    total_margin_isk = Decimal(0)
    active_orders = IndustryOrder.objects.filter(
        fulfilled_at__isnull=True
    ).prefetch_related("items__assignments")
    for order in active_orders:
        for item in order.items.all():
            line_unit, line_margin = order_line_list_targets(item)
            for a in item.assignments.all():
                unit = a.target_unit_price or line_unit
                margin = a.target_estimated_margin or line_margin
                q = Decimal(a.quantity)
                if unit is not None:
                    total_order_isk += q * unit
                if margin is not None:
                    total_margin_isk += q * margin
    return SummaryTotals(
        total_order_amount_isk=total_order_isk,
        total_available_margin_isk=total_margin_isk,
    )


def get_order_summary_message(
    *,
    max_section_lines: int = 35,
) -> str:
    """Full Discord markdown message: headers, blurbs, bullets, footer totals."""
    active = get_active_order_display_items()
    unassigned = get_unassigned_order_items()
    totals = get_summary_totals_for_active_orders()

    def trunc(lines: list[str]) -> list[str]:
        if len(lines) <= max_section_lines:
            return lines
        extra = len(lines) - max_section_lines
        return lines[:max_section_lines] + [f"- … and {extra} more"]

    active_lines = [
        (
            f"- `{row.public_short_code}` [{row.location_label}] "
            f"{row.group_names_csv} {format_margin_profit_parenthetical(row.profit_isk)}"
        )
        for row in active
    ]
    if not active_lines:
        active_lines = ["- *(none)*"]
    else:
        active_lines = trunc(active_lines)

    un_lines = [
        (
            f"- `{row.public_short_code}` [{row.location_label}] "
            f"{row.eve_type_name} x{row.unassigned_quantity} "
            f"{format_margin_profit_parenthetical(row.profit_isk)}"
        )
        for row in unassigned
    ]
    if not un_lines:
        un_lines = ["- *(none)*"]
    else:
        un_lines = trunc(un_lines)

    return "\n".join(
        [
            "# Industry order summary",
            "",
            "## Active orders",
            "Open builds, sorted by where they’re headed.",
            "",
            *active_lines,
            "",
            "## Unassigned order items",
            "These order items still need someone to take the work.",
            "",
            *un_lines,
            "",
            f"**Total order amount:** {format_isk_billions_trimmed(totals.total_order_amount_isk)}",
            f"**Total available margin:** {format_isk_billions_trimmed(totals.total_available_margin_isk)}",
        ]
    )
