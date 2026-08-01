"""GET /orders - LP buyback market order book."""

from typing import List, Optional

from ninja import Query

from industry.endpoints.loyalty.schemas import LoyaltyMarketOrderResponse
from industry.endpoints.loyalty.serialization import market_order_response
from industry.helpers.lp_market_orders import ACTIVE_STATUSES
from industry.models import IndustryLoyaltyPointMarketOrder

PATH = "/orders"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List loyalty-point buy/sell market orders",
    "response": {200: List[LoyaltyMarketOrderResponse]},
}


def get_orders(
    request,
    side: Optional[str] = Query(None),
    loyalty_point_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
):
    qs = IndustryLoyaltyPointMarketOrder.objects.select_related(
        "loyalty_point", "created_by", "claimed_by"
    ).prefetch_related("claims__claimed_by")
    if side:
        qs = qs.filter(side=side)
    if loyalty_point_id is not None:
        qs = qs.filter(loyalty_point_id=loyalty_point_id)
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        qs = qs.filter(status__in=statuses)
    else:
        qs = qs.filter(status__in=ACTIVE_STATUSES)
    return [market_order_response(o) for o in qs]
