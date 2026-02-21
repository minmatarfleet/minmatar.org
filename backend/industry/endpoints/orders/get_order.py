"""GET /{order_id} - fetch one order with items and who committed to it (public)."""

from app.errors import ErrorResponse

from industry.endpoints.orders.schemas import (
    AssignmentResponse,
    OrderDetailResponse,
    OrderItemResponse,
    OrderLocationResponse,
)
from industry.models import IndustryOrder

PATH = "{int:order_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get a single order with items and who has committed to each item",
    "response": {
        200: OrderDetailResponse,
        404: ErrorResponse,
    },
}


def get_order(request, order_id: int):
    try:
        order = (
            IndustryOrder.objects.filter(pk=order_id)
            .select_related("character", "location")
            .prefetch_related(
                "items__eve_type",
                "items__assignments__character",
            )
            .get()
        )
    except IndustryOrder.DoesNotExist:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    return 200, OrderDetailResponse(
        id=order.pk,
        created_at=order.created_at,
        needed_by=order.needed_by,
        fulfilled_at=order.fulfilled_at,
        character_id=order.character.character_id,
        character_name=order.character.character_name,
        location=(
            OrderLocationResponse(
                location_id=order.location.location_id,
                location_name=order.location.location_name,
            )
            if order.location_id
            else None
        ),
        items=[
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
        ],
    )
