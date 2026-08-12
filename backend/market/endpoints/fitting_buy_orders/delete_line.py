"""DELETE /fitting-buy-orders/{order_id}/lines/{line_id}."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from market.endpoints.fitting_buy_orders.common import (
    get_order_or_404,
    require_owner,
)
from market.helpers.fitting_buy_plan import sync_order_items
from market.helpers.fitting_buy_serialize import (
    FittingBuyOrderDetailSchema,
    serialize_order_detail,
)
from market.models.fitting_buy_order import FittingBuyOrderLine

PATH = "/fitting-buy-orders/{order_id}/lines/{line_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "response": {
        200: FittingBuyOrderDetailSchema,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Remove a fitting line from a buy order",
}


def delete_fitting_buy_line(request, order_id: int, line_id: int):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    denied = require_owner(request, order)
    if denied:
        return denied

    line = FittingBuyOrderLine.objects.filter(order=order, pk=line_id).first()
    if line is None:
        return 404, ErrorResponse(detail="Line not found.")
    line.delete()
    sync_order_items(order)
    return serialize_order_detail(order, request.user)
