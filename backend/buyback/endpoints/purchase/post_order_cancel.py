"""POST /stock/orders/{order_id}/cancel – owner or operator cancels."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from buyback.endpoints.purchase.serialization import order_response
from buyback.endpoints.schemas import BuybackPurchaseOrderResponse
from buyback.helpers.auth import can_manage_stock_sales
from buyback.helpers.purchase_orders import (
    PurchaseOrderError,
    cancel_purchase_order,
)
from buyback.models import BuybackPurchaseOrder

PATH = "/orders/{order_id}/cancel"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Cancel a pending buyback purchase",
    "auth": AuthBearer(),
    "response": {
        200: BuybackPurchaseOrderResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_order_cancel(request, order_id: int):
    order = (
        BuybackPurchaseOrder.objects.prefetch_related("lines")
        .filter(pk=order_id)
        .first()
    )
    if order is None:
        return 404, ErrorResponse(detail="Purchase order not found.")
    is_owner = order.created_by_id == request.user.id
    if not is_owner and not can_manage_stock_sales(request.user):
        return 403, ErrorResponse(detail="feature_denied")
    try:
        cancel_purchase_order(order)
    except PurchaseOrderError as exc:
        return 400, ErrorResponse(detail=str(exc))
    order.refresh_from_db()
    return order_response(order)
