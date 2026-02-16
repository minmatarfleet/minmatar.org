"""GET "" - list industry orders and their location."""

from typing import List

from authentication import AuthBearer

from industry.endpoints.orders.schemas import (
    OrderListItemResponse,
    OrderLocationResponse,
)
from industry.models import IndustryOrder

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List industry orders for the authenticated user's characters, with location",
    "auth": AuthBearer(),
    "response": {200: List[OrderListItemResponse]},
}


def get_orders(request):
    orders = (
        IndustryOrder.objects.filter(character__user=request.user)
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
