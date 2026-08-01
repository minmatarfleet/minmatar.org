"""POST /orders - create an LP buy or sell market order."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature
from industry.endpoints.loyalty.auth_helpers import can_manage_buyback
from industry.endpoints.loyalty.schemas import (
    CreateLoyaltyMarketOrderRequest,
    LoyaltyMarketOrderResponse,
)
from industry.endpoints.loyalty.serialization import market_order_response
from industry.helpers.lp_market_orders import LpMarketOrderError, create_order
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointMarketOrder,
)

PATH = "/orders"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Create a loyalty-point buy or sell market order",
    "auth": AuthBearer(),
    "response": {
        201: LoyaltyMarketOrderResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_orders(request, payload: CreateLoyaltyMarketOrderRequest):
    side = (payload.side or "").strip().lower()
    if side not in (
        IndustryLoyaltyPointMarketOrder.Side.BUY,
        IndustryLoyaltyPointMarketOrder.Side.SELL,
    ):
        return 400, ErrorResponse(detail="side must be 'buy' or 'sell'.")

    if side == IndustryLoyaltyPointMarketOrder.Side.SELL:
        denied = require_feature(request.user, "industry.loyalty.trade")
        if denied:
            return denied
    elif not can_manage_buyback(request.user):
        return 403, ErrorResponse(detail="feature_denied")

    if payload.quantity is None or int(payload.quantity) <= 0:
        return 400, ErrorResponse(
            detail="quantity must be a positive integer."
        )

    currency = IndustryLoyaltyPoint.objects.filter(
        pk=payload.loyalty_point_id, is_active=True
    ).first()
    if not currency:
        return 404, ErrorResponse(detail="Loyalty point currency not found.")

    isk_per_lp = payload.isk_per_lp
    if isk_per_lp is None or int(isk_per_lp) <= 0:
        isk_per_lp = currency.default_isk_per_lp
    else:
        isk_per_lp = int(isk_per_lp)

    try:
        order = create_order(
            currency=currency,
            side=side,
            quantity=int(payload.quantity),
            isk_per_lp=isk_per_lp,
            created_by=request.user,
            notes=(payload.notes or "").strip(),
        )
    except LpMarketOrderError as exc:
        return 400, ErrorResponse(detail=str(exc))
    order = (
        IndustryLoyaltyPointMarketOrder.objects.select_related(
            "loyalty_point", "created_by", "claimed_by"
        )
        .prefetch_related("claims__claimed_by")
        .get(pk=order.pk)
    )
    return 201, market_order_response(order)
