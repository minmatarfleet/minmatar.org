"""GET /fitting-buy-orders — list globally visible fitting buy orders."""

from django.db.models import Count

from authentication import AuthBearer
from market.helpers.fitting_buy_serialize import (
    FittingBuyOrderListItemSchema,
    serialize_order_list_item,
)
from market.models.fitting_buy_order import FittingBuyOrder

PATH = "/fitting-buy-orders"
METHOD = "get"
ROUTE_SPEC = {
    "response": list[FittingBuyOrderListItemSchema],
    "auth": AuthBearer(),
    "summary": "List fitting buy orders (global)",
}


def get_fitting_buy_orders(
    request, status: str | None = None, mine: bool = False
):
    qs = (
        FittingBuyOrder.objects.select_related("owner")
        .prefetch_related("lines__fitting")
        .annotate(line_count=Count("lines"))
    )
    if status:
        qs = qs.filter(status=status)
    if mine:
        qs = qs.filter(owner=request.user)
    return [
        serialize_order_list_item(order, request.user) for order in qs[:200]
    ]
