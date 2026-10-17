"""GET /stats - rolling LP buyback order stats (count, close time, price)."""

from typing import Optional

from ninja import Query

from industry.endpoints.loyalty.schemas import LoyaltyOrderStatsResponse
from industry.helpers.lp_order_stats import DEFAULT_STATS_DAYS, order_stats

PATH = "/stats"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Rolling loyalty-point order stats by standard / express tier",
    "response": {200: LoyaltyOrderStatsResponse},
}


def get_stats(
    request,
    loyalty_point_id: Optional[int] = Query(None),
    days: int = Query(DEFAULT_STATS_DAYS, ge=1, le=365),
):
    return order_stats(loyalty_point_id=loyalty_point_id, days=days)
