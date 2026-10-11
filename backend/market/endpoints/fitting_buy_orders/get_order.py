"""GET /fitting-buy-orders/{order_id} — order detail."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from market.endpoints.fitting_buy_orders.common import get_order_or_404
from market.helpers.fitting_buy_plan import sync_order_items
from market.helpers.fitting_buy_serialize import (
    FittingBuyOrderDetailSchema,
    serialize_order_detail,
)

PATH = "/fitting-buy-orders/{order_id}"
METHOD = "get"
ROUTE_SPEC = {
    "response": {200: FittingBuyOrderDetailSchema, 404: ErrorResponse},
    "auth": AuthBearer(),
    "summary": "Get a fitting buy order",
}


def get_fitting_buy_order(request, order_id: int):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    sync_order_items(order)
    return serialize_order_detail(order, request.user)
