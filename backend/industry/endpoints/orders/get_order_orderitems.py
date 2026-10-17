"""GET /{order_id}/orderitems - list order items with details and assignments (public)."""

from typing import List

from app.errors import ErrorResponse

from industry.endpoints.orders.schemas import OrderItemResponse
from industry.endpoints.orders.serialization import order_item_to_response
from industry.helpers.order_profit_breakdown import (
    stored_profit_per_unit_by_type,
)
from industry.models import IndustryOrder

PATH = "{int:order_id}/orderitems"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List order items with details and assignments",
    "response": {
        200: List[OrderItemResponse],
        404: ErrorResponse,
    },
}


def get_order_orderitems(request, order_id: int):
    try:
        order = (
            IndustryOrder.objects.filter(pk=order_id)
            .prefetch_related(
                "items__eve_type",
                "items__assignments__character",
            )
            .get()
        )
    except IndustryOrder.DoesNotExist:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    profit_by_type = stored_profit_per_unit_by_type(order)
    return 200, [
        order_item_to_response(order, item, profit_by_type)
        for item in order.items.all()
    ]
