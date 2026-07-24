"""GET /profit-summary — profit rollup from stored per-order snapshots (public)."""

from datetime import date
from typing import Optional

from app.errors import ErrorResponse
from ninja import Query

from industry.endpoints.orders.schemas import (
    OrdersProfitSummaryResponse,
    ProfitSummaryOrderResponse,
    ProfitSummaryRowResponse,
    ProfitSummaryTotalsResponse,
)
from industry.helpers.order_profit_breakdown import (
    compose_orders_profit_summary_from_snapshots,
)

PATH = "profit-summary"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "Profit summary for industry orders from stored snapshots "
        "(filterable by needed_by / order ids)"
    ),
    "response": {
        200: OrdersProfitSummaryResponse,
        400: ErrorResponse,
    },
}


def get_orders_profit_summary(
    request,
    needed_by_from: Optional[date] = Query(None),
    needed_by_to: Optional[date] = Query(None),
    open_only: bool = Query(True),
    order_ids: Optional[str] = Query(
        None, description="Comma-separated order IDs to include"
    ),
):
    try:
        summary = compose_orders_profit_summary_from_snapshots(
            needed_by_from=needed_by_from,
            needed_by_to=needed_by_to,
            open_only=open_only,
            order_ids=order_ids,
        )
    except ValueError as exc:
        return 400, ErrorResponse(detail=str(exc))

    return OrdersProfitSummaryResponse(
        orders=[
            ProfitSummaryOrderResponse(
                id=o.id,
                public_short_code=o.public_short_code,
                needed_by=o.needed_by,
                location_label=o.location_label,
                fulfilled_at=o.fulfilled_at,
                item_count=o.item_count,
                item_type_ids=o.item_type_ids,
                included=o.included,
            )
            for o in summary.orders
        ],
        rows=[
            ProfitSummaryRowResponse(
                name=r.name,
                type_id=r.type_id,
                kind=r.kind,
                qty=r.qty,
                isk_per_lp=r.isk_per_lp,
                cost_per=r.cost_per,
                unit_price=r.unit_price,
                price_source=r.price_source,
                profit_per=r.profit_per,
                order_profit=r.order_profit,
                note=r.note,
            )
            for r in summary.rows
        ],
        totals=ProfitSummaryTotalsResponse(
            total_order_amount=summary.totals.total_order_amount,
            total_profit=summary.totals.total_profit,
            line_count=summary.totals.line_count,
            total_qty=summary.totals.total_qty,
            best_name=summary.totals.best_name,
            best_profit=summary.totals.best_profit,
            worst_name=summary.totals.worst_name,
            worst_profit=summary.totals.worst_profit,
        ),
        assumptions=summary.assumptions,
        facility_key=summary.facility_key,
        compressed=summary.compressed,
    )
