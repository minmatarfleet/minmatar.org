"""GET /orders/{order_id} - one LP buyback order (the order tracker)."""

from app.errors import ErrorResponse

from industry.endpoints.loyalty.schemas import LoyaltyMarketOrderResponse
from industry.endpoints.loyalty.serialization import market_order_response
from industry.helpers.lp_buyback_discord import lp_buyback_thread_url
from industry.models import IndustryLoyaltyPointMarketOrder

PATH = "/orders/{order_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get one loyalty-point market order",
    "response": {200: LoyaltyMarketOrderResponse, 404: ErrorResponse},
}


def get_order(request, order_id: int):
    """Public, like the order book it is listed in."""
    order = (
        IndustryLoyaltyPointMarketOrder.objects.select_related(
            "loyalty_point", "created_by", "claimed_by"
        )
        .prefetch_related("claims__claimed_by")
        .filter(pk=order_id)
        .first()
    )
    if not order:
        return 404, ErrorResponse(detail="Order not found.")
    response = market_order_response(order)
    response.discord_thread_url = lp_buyback_thread_url(order)
    return 200, response
