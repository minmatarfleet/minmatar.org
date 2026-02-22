"""GET "" - list industry orders with location, flat items and assignees (public)."""

from typing import List

from industry.endpoints.orders.schemas import (
    OrderAssigneeResponse,
    OrderItemQuantityResponse,
    OrderListItemResponse,
    OrderLocationResponse,
)
from industry.models import IndustryOrder

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List all industry orders with location, items and assignees",
    "response": {200: List[OrderListItemResponse]},
}


def get_orders(request):
    orders = (
        IndustryOrder.objects.all()
        .select_related("character", "location")
        .prefetch_related(
            "items__eve_type",
            "items__assignments__character",
        )
        .order_by("-created_at")
    )
    result = []
    for order in orders:
        items_flat = [
            OrderItemQuantityResponse(
                eve_type_id=item.eve_type_id,
                eve_type_name=item.eve_type.name,
                quantity=item.quantity,
            )
            for item in order.items.all()
        ]
        seen = set()
        assigned_to_flat = []
        for item in order.items.all():
            for a in item.assignments.all():
                cid = a.character.character_id
                if cid not in seen:
                    seen.add(cid)
                    assigned_to_flat.append(
                        OrderAssigneeResponse(
                            character_id=cid,
                            character_name=a.character.character_name,
                        )
                    )
        result.append(
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
                items=items_flat,
                assigned_to=assigned_to_flat,
            )
        )
    return result
