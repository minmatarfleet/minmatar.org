"""POST /{order_id}/profit-breakdown/refresh — recompute stored profit snapshot."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature
from industry.endpoints.orders.schemas import (
    OrderProfitBreakdownResponse,
    ProfitSummaryRowResponse,
    ProfitSummaryTotalsResponse,
)
from industry.helpers.order_profit_breakdown import (
    ProfitBreakdownRefreshNotAllowed,
    refresh_order_profit_breakdown,
)
from industry.models import IndustryOrder

PATH = "{int:order_id}/profit-breakdown/refresh"
METHOD = "post"
ROUTE_SPEC = {
    "summary": (
        "Refresh the stored profit/price breakdown for an order "
        "(open orders, or when no snapshot exists yet)"
    ),
    "auth": AuthBearer(),
    "response": {
        200: OrderProfitBreakdownResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def _payload_to_response(payload: dict) -> OrderProfitBreakdownResponse:
    totals = payload.get("totals") or {}
    return OrderProfitBreakdownResponse(
        rows=[
            ProfitSummaryRowResponse(
                name=r.get("name") or "",
                type_id=int(r["type_id"]),
                kind=r.get("kind") or "T1",
                qty=int(r.get("qty") or 0),
                isk_per_lp=r.get("isk_per_lp"),
                cost_per=int(r.get("cost_per") or 0),
                unit_price=int(r.get("unit_price") or 0),
                price_source=r.get("price_source") or "jita",
                profit_per=int(r.get("profit_per") or 0),
                order_profit=int(r.get("order_profit") or 0),
                note=r.get("note"),
            )
            for r in (payload.get("rows") or [])
        ],
        totals=ProfitSummaryTotalsResponse(
            total_order_amount=int(totals.get("total_order_amount") or 0),
            total_profit=int(totals.get("total_profit") or 0),
            line_count=int(totals.get("line_count") or 0),
            total_qty=int(totals.get("total_qty") or 0),
            best_name=totals.get("best_name"),
            best_profit=totals.get("best_profit"),
            worst_name=totals.get("worst_name"),
            worst_profit=totals.get("worst_profit"),
        ),
        assumptions=list(payload.get("assumptions") or []),
        facility_key=str(payload.get("facility_key") or "amamake"),
        compressed=bool(payload.get("compressed", True)),
    )


def post_order_profit_breakdown_refresh(request, order_id: int):
    denied = require_feature(request.user, "industry.order.submit")
    if denied:
        return denied

    try:
        order = IndustryOrder.objects.get(pk=order_id)
    except IndustryOrder.DoesNotExist:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")

    try:
        payload = refresh_order_profit_breakdown(order)
    except ProfitBreakdownRefreshNotAllowed as exc:
        return 400, ErrorResponse(detail=str(exc))
    except ValueError as exc:
        return 400, ErrorResponse(detail=str(exc))

    return 200, _payload_to_response(payload)
