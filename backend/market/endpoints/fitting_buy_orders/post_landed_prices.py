"""POST /fitting-buy-orders/{order_id}/landed-prices — paste actual prices."""

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from market.endpoints.fitting_buy_orders.common import (
    get_order_or_404,
    require_owner,
)
from market.helpers.fitting_buy_prices import apply_landed_prices
from market.helpers.fitting_buy_serialize import (
    FittingBuyOrderDetailSchema,
    serialize_order_detail,
)

PATH = "/fitting-buy-orders/{order_id}/landed-prices"
METHOD = "post"


class LandedPricesRequest(Schema):
    paste: str


class LandedPricesResponse(Schema):
    updated: int
    unresolved: list[str]
    order: FittingBuyOrderDetailSchema


ROUTE_SPEC = {
    "response": {
        200: LandedPricesResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Paste landed Jita unit prices onto shopping lines",
}


def post_fitting_buy_landed_prices(
    request, order_id: int, payload: LandedPricesRequest
):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    denied = require_owner(request, order)
    if denied:
        return denied
    if not payload.paste.strip():
        return 400, ErrorResponse(detail="Paste is empty.")

    updated, unresolved = apply_landed_prices(order, payload.paste)
    order.refresh_from_db()
    return {
        "updated": updated,
        "unresolved": unresolved,
        "order": serialize_order_detail(order, request.user),
    }
