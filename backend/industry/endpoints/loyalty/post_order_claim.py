"""POST /orders/{order_id}/claim - Conversion Team claims LP on an open order."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.loyalty.auth_helpers import can_manage_buyback
from industry.endpoints.loyalty.schemas import (
    ClaimLoyaltyMarketOrderRequest,
    LoyaltyMarketOrderResponse,
)
from industry.endpoints.loyalty.serialization import market_order_response
from industry.helpers.lp_market_orders import LpMarketOrderError, claim_order
from industry.models import IndustryLoyaltyPointMarketOrder

PATH = "/orders/{order_id}/claim"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Claim LP on an open loyalty-point market order",
    "auth": AuthBearer(),
    "response": {
        200: LoyaltyMarketOrderResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_order_claim(
    request,
    order_id: int,
    payload: ClaimLoyaltyMarketOrderRequest,
):
    if not can_manage_buyback(request.user):
        return 403, ErrorResponse(detail="feature_denied")

    order = (
        IndustryLoyaltyPointMarketOrder.objects.filter(pk=order_id)
        .prefetch_related("claims__claimed_by")
        .first()
    )
    if not order:
        return 404, ErrorResponse(detail="Order not found.")

    try:
        order = claim_order(
            order,
            request.user,
            amount=payload.amount,
            destination_character_name=payload.destination_character_name
            or "",
            destination_corporation_name=payload.destination_corporation_name
            or "",
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
    return 200, market_order_response(order)
