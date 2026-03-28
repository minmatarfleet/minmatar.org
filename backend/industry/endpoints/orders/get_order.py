"""GET /{order_id} - fetch one order with items and who committed to it (public)."""

from app.errors import ErrorResponse

from industry.endpoints.orders.schemas import (
    OrderDetailResponse,
    OrderLocationResponse,
)
from industry.endpoints.orders.serialization import order_item_to_response
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
        public_short_code=order.public_short_code,
        contract_to=order.contract_to,
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
            order_item_to_response(order, item) for item in order.items.all()
        ],
    )
