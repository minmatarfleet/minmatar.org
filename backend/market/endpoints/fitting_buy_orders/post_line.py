"""POST /fitting-buy-orders/{order_id}/lines — add or update a fit line."""

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from fittings.models import EveFitting
from market.endpoints.fitting_buy_orders.common import (
    get_order_or_404,
    require_owner,
)
from market.helpers.fitting_buy_check import ensure_jita_check
from market.helpers.fitting_buy_plan import sync_order_items
from market.helpers.fitting_buy_serialize import (
    FittingBuyOrderDetailSchema,
    serialize_order_detail,
)
from market.models.fitting_buy_order import FittingBuyOrderLine

PATH = "/fitting-buy-orders/{order_id}/lines"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        200: FittingBuyOrderDetailSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Add or update a fitting line on a buy order",
}


class UpsertFittingBuyLineRequest(Schema):
    fitting_id: int
    quantity: int = 1


def post_fitting_buy_line(
    request, order_id: int, payload: UpsertFittingBuyLineRequest
):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    denied = require_owner(request, order)
    if denied:
        return denied

    if payload.quantity < 1:
        return 400, ErrorResponse(detail="Quantity must be at least 1.")

    fitting = EveFitting.objects.filter(pk=payload.fitting_id).first()
    if fitting is None:
        return 404, ErrorResponse(detail="Fitting not found.")

    line, created = FittingBuyOrderLine.objects.get_or_create(
        order=order,
        fitting=fitting,
        defaults={
            "quantity": payload.quantity,
            "sort_order": order.lines.count(),
        },
    )
    if not created:
        line.quantity = payload.quantity
        fields = ["quantity"]
        if (
            line.swap_hull_qty is not None
            and line.swap_hull_qty > payload.quantity
        ):
            line.swap_hull_qty = payload.quantity
            fields.append("swap_hull_qty")
        line.save(update_fields=fields)

    sync_order_items(order)
    ensure_jita_check(order, request.user, quiet=True)
    return serialize_order_detail(order, request.user)
