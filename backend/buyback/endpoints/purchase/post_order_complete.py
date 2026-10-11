"""POST /stock/orders/{order_id}/complete – operator marks a sale done."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from buyback.endpoints.purchase.serialization import order_response
from buyback.endpoints.schemas import BuybackPurchaseOrderResponse
from buyback.helpers.auth import can_manage_stock_sales
from buyback.helpers.purchase_orders import (
    PurchaseOrderError,
    complete_purchase_order,
)
from buyback.models import BuybackPurchaseOrder

PATH = "/orders/{order_id}/complete"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Mark a pending buyback purchase as contracted",
    "auth": AuthBearer(),
    "response": {
        200: BuybackPurchaseOrderResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_order_complete(request, order_id: int):
    if not can_manage_stock_sales(request.user):
        return 403, ErrorResponse(detail="feature_denied")
    order = (
        BuybackPurchaseOrder.objects.prefetch_related("lines")
        .filter(pk=order_id)
        .first()
    )
    if order is None:
        return 404, ErrorResponse(detail="Purchase order not found.")
    try:
        complete_purchase_order(order, request.user)
    except PurchaseOrderError as exc:
        return 400, ErrorResponse(detail=str(exc))
    order.refresh_from_db()
    return order_response(order)
