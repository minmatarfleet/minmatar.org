"""GET /stock/orders – list buyback purchase orders."""

from typing import Optional

from ninja import Query

from authentication import AuthBearer
from buyback.endpoints.purchase.serialization import order_response
from buyback.endpoints.schemas import BuybackPurchaseOrderListResponse
from buyback.helpers.auth import can_manage_stock_sales
from buyback.models import BuybackPurchaseOrder

PATH = "/orders"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List own purchase orders, or all pending if operator",
    "auth": AuthBearer(),
    "response": {200: BuybackPurchaseOrderListResponse},
}


def get_orders(request, status: Optional[str] = Query("pending")):
    qs = BuybackPurchaseOrder.objects.prefetch_related("lines").select_related(
        "created_by"
    )
    if can_manage_stock_sales(request.user):
        wanted = (status or "pending").strip().lower()
        if wanted and wanted != "all":
            qs = qs.filter(status=wanted)
    else:
        qs = qs.filter(created_by=request.user)
    orders = list(qs[:100])
    return BuybackPurchaseOrderListResponse(
        orders=[order_response(order) for order in orders],
        count=len(orders),
    )
