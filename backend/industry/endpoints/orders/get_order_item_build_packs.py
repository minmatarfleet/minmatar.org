"""GET /{order_id}/orderitems/{order_item_id}/build-packs — BUILD packs (public)."""

from typing import List

from app.errors import ErrorResponse
from industry.endpoints.orders.schemas import BuildPackResponse
from industry.helpers.build_packs import match_build_packs_for_item
from industry.models import IndustryOrderItem

PATH = "{int:order_id}/orderitems/{int:order_item_id}/build-packs"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "Outstanding BUILD alliance BPC / material pack contracts "
        "matching an order line (title heuristic, informational)"
    ),
    "response": {
        200: List[BuildPackResponse],
        404: ErrorResponse,
    },
}


def get_order_item_build_packs(request, order_id: int, order_item_id: int):
    order_item = (
        IndustryOrderItem.objects.filter(pk=order_item_id, order_id=order_id)
        .select_related("eve_type", "eve_type__eve_group")
        .first()
    )
    if order_item is None:
        return 404, ErrorResponse(
            detail=f"Order item {order_item_id} not found on order {order_id}."
        )
    return 200, [
        BuildPackResponse(
            title=pack.title,
            count=pack.count,
            price=pack.price,
            location_name=pack.location_name,
        )
        for pack in match_build_packs_for_item(order_item)
    ]
