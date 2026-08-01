"""GET /stockpiles - active alliance LP stockpile accounts."""

from typing import List

from industry.endpoints.orders.schemas import OrderLpStockpileResponse
from industry.endpoints.orders.serialization import lp_stockpile_to_response
from industry.helpers.order_lp_stockpiles import resolve_all_lp_stockpiles

PATH = "/stockpiles"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List active loyalty-point stockpile accounts and balances",
    "response": {200: List[OrderLpStockpileResponse]},
}


def get_stockpiles(request):
    return [
        lp_stockpile_to_response(row) for row in resolve_all_lp_stockpiles()
    ]
