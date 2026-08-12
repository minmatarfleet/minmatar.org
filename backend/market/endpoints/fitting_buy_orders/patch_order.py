"""PATCH /fitting-buy-orders/{order_id} — update order metadata / stock."""

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
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
from market.models.fitting_buy_order import FittingBuyOrderStatus

PATH = "/fitting-buy-orders/{order_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "response": {
        200: FittingBuyOrderDetailSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Update a fitting buy order",
}


class PatchFittingBuyOrderRequest(Schema):
    notes: str | None = None
    status: str | None = None
    stock_paste: str | None = None
    include_hull: bool | None = None


def patch_fitting_buy_order(
    request, order_id: int, payload: PatchFittingBuyOrderRequest
):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    denied = require_owner(request, order)
    if denied:
        return denied

    fields = []
    if payload.notes is not None:
        order.notes = payload.notes
        fields.append("notes")
    if payload.status is not None:
        valid = {c.value for c in FittingBuyOrderStatus}
        if payload.status not in valid:
            return 400, ErrorResponse(detail="Invalid status.")
        order.status = payload.status
        fields.append("status")
    if payload.stock_paste is not None:
        order.stock_paste = payload.stock_paste
        fields.append("stock_paste")
    if payload.include_hull is not None:
        order.include_hull = payload.include_hull
        fields.append("include_hull")

    if fields:
        fields.append("updated_at")
        order.save(update_fields=fields)
        if "stock_paste" in fields or "include_hull" in fields:
            sync_order_items(order)
            ensure_jita_check(order, request.user, quiet=True)

    return serialize_order_detail(order, request.user)
