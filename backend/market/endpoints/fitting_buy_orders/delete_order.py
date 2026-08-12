"""DELETE /fitting-buy-orders/{order_id} — remove an order."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from market.endpoints.fitting_buy_orders.common import (
    get_order_or_404,
    require_owner,
)

PATH = "/fitting-buy-orders/{order_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "response": {
        204: None,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Delete a fitting buy order",
}


def delete_fitting_buy_order(request, order_id: int):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    denied = require_owner(request, order)
    if denied:
        return denied

    order.delete()
    return 204, None
