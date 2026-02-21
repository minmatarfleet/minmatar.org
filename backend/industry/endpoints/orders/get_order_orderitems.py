"""GET /{order_id}/orderitems - list order items with details and assignments (public)."""

from typing import List

from app.errors import ErrorResponse

from industry.endpoints.orders.schemas import (
    AssignmentResponse,
    OrderItemResponse,
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
    return 200, [
        OrderItemResponse(
            id=item.pk,
            eve_type_id=item.eve_type_id,
            eve_type_name=item.eve_type.name,
            quantity=item.quantity,
            assignments=[
                AssignmentResponse(
                    character_id=a.character.character_id,
                    character_name=a.character.character_name,
                    quantity=a.quantity,
                )
                for a in item.assignments.all()
            ],
        )
        for item in order.items.all()
    ]
