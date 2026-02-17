"""GET /orders/{order_id}/breakdown - nested material breakdown for the whole order."""

from collections import defaultdict
from typing import List

from eveuniverse.models import EveType

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.breakdown.schemas import (
    NestedBreakdownNode,
    OrderBreakdownResponse,
)
from industry.helpers.type_breakdown import (
    enrich_breakdown_with_industry_product_ids,
    get_breakdown_for_industry_product,
)
from industry.models import IndustryOrder

PATH = "{int:order_id}/breakdown"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Nested material breakdown for all items in the order",
    "auth": AuthBearer(),
    "response": {
        200: OrderBreakdownResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_order_breakdown(request, order_id: int):
    try:
        order = (
            IndustryOrder.objects.filter(pk=order_id)
            .select_related("character")
            .prefetch_related("items__eve_type")
            .get()
        )
    except IndustryOrder.DoesNotExist:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    if order.character.user_id != request.user.id:
        return 403, ErrorResponse(
            detail="You may only view orders for your own characters."
        )
    by_type: dict[int, int] = defaultdict(int)
    for item in order.items.all():
        by_type[item.eve_type_id] += item.quantity
    if not by_type:
        return 200, OrderBreakdownResponse(roots=[])
    roots: List[NestedBreakdownNode] = []
    for type_id in sorted(by_type.keys()):
        try:
            eve_type = EveType.objects.get(id=type_id)
        except EveType.DoesNotExist:
            continue
        tree = get_breakdown_for_industry_product(
            eve_type, quantity=by_type[type_id]
        )
        enrich_breakdown_with_industry_product_ids(tree)
        roots.append(NestedBreakdownNode.from_breakdown_dict(tree))
    return 200, OrderBreakdownResponse(roots=roots)
