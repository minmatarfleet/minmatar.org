"""DELETE /orders/{order_id}/claim - release claims and reopen the order."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.loyalty.auth_helpers import can_manage_buyback
from industry.endpoints.loyalty.schemas import LoyaltyMarketOrderResponse
from industry.endpoints.loyalty.serialization import market_order_response
from industry.helpers.lp_market_orders import (
    LpMarketOrderError,
    release_order_claims,
)
from industry.models import IndustryLoyaltyPointMarketOrder

PATH = "/orders/{order_id}/claim"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": (
        "Release LP market order claims and reopen the order "
        "(before LP is marked received)"
    ),
    "auth": AuthBearer(),
    "response": {
        200: LoyaltyMarketOrderResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def delete_order_claim(request, order_id: int):
    order = (
        IndustryLoyaltyPointMarketOrder.objects.filter(pk=order_id)
        .prefetch_related("claims__claimed_by")
        .first()
    )
    if not order:
        return 404, ErrorResponse(detail="Order not found.")

    is_manager = can_manage_buyback(request.user)
    is_claimer = order.claims.filter(claimed_by=request.user).exists()
    if not (is_manager or is_claimer):
        return 403, ErrorResponse(detail="feature_denied")

    try:
        order = release_order_claims(
            order,
            request.user,
            release_all=is_manager,
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
