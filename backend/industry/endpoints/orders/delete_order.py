"""DELETE /{order_id} - delete an industry order."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.models import IndustryOrder

PATH = "{int:order_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Delete an industry order. Only the order's character owner may delete it.",
    "auth": AuthBearer(),
    "response": {204: None, 403: ErrorResponse, 404: ErrorResponse},
}


def delete_order(request, order_id: int):
    try:
        order = IndustryOrder.objects.get(pk=order_id)
    except IndustryOrder.DoesNotExist:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    if order.character.user_id != request.user.id:
        return 403, ErrorResponse(
            detail="You may only delete orders for your own characters."
        )
    order.delete()
    return 204, None
