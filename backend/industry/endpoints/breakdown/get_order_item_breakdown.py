"""GET /orders/{order_id}/items/{item_id}/breakdown - nested breakdown for one order item."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.breakdown.schemas import NestedBreakdownNode
from industry.helpers.type_breakdown import get_nested_breakdown
from industry.models import IndustryOrder

PATH = "{int:order_id}/items/{int:item_id}/breakdown"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Nested material breakdown for a single order line item",
    "auth": AuthBearer(),
    "response": {
        200: NestedBreakdownNode,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_order_item_breakdown(request, order_id: int, item_id: int):
    try:
        order = (
            IndustryOrder.objects.filter(pk=order_id)
            .select_related("character")
            .prefetch_related("items__eve_type")
            .get()
        )
    except IndustryOrder.DoesNotExist:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    if order.character.user_id != request.user.id:
        return 403, ErrorResponse(
            detail="You may only view orders for your own characters."
        )
    item = order.items.filter(pk=item_id).select_related("eve_type").first()
    if not item:
        return 404, ErrorResponse(detail=f"Order item {item_id} not found.")
    tree = get_nested_breakdown(item.eve_type, quantity=item.quantity)
    return 200, NestedBreakdownNode(**tree)
