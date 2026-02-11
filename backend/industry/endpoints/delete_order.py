"""DELETE /orders/{order_id} - delete an industry order."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.models import IndustryOrder
from ninja import Router

router = Router(tags=["Industry - Orders"])


@router.delete(
    "/{order_id}",
    response={204: None, 403: ErrorResponse, 404: ErrorResponse},
    auth=AuthBearer(),
)
def delete_order(request, order_id: int):
    """Delete an industry order. Only the order's character owner may delete it."""
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
