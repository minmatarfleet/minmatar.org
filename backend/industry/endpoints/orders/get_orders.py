"""GET "" - list industry orders and their location (public)."""

from typing import List

from industry.endpoints.orders.schemas import (
    OrderListItemResponse,
    OrderLocationResponse,
)
from industry.models import IndustryOrder

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List all industry orders with location",
    "response": {200: List[OrderListItemResponse]},
}


def get_orders(request):
    orders = (
        IndustryOrder.objects.all()
        .select_related("character", "location")
        .order_by("-created_at")
    )
    return [
        OrderListItemResponse(
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
        )
        for order in orders
    ]
