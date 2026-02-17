from collections import defaultdict
from datetime import timedelta
from typing import List

from django.utils import timezone
from eveuniverse.models import EveType
from ninja import Router
from pydantic import BaseModel

from industry.helpers.type_breakdown import get_breakdown_for_industry_product
from industry.models import IndustryOrder

router = Router(tags=["Industry - Orders Summary"])


class NestedBreakdownNode(BaseModel):
    name: str
    type_id: int
    quantity: int
    source: str
    depth: int
    children: List["NestedBreakdownNode"] = []


NestedBreakdownNode.model_rebuild()


class SummaryNestedResponse(BaseModel):
    roots: List[NestedBreakdownNode]


@router.get("/nested", response=SummaryNestedResponse)
def get_orders_breakdown_summary_nested(request):
    """Aggregated material breakdown for all order items in the last 30 days (nested per product type)."""
    since = timezone.now() - timedelta(days=30)
    orders = IndustryOrder.objects.filter(
        created_at__gte=since
    ).prefetch_related("items__eve_type")
    by_type: dict[int, int] = defaultdict(int)
    for order in orders:
        for item in order.items.all():
            by_type[item.eve_type_id] += item.quantity
    if not by_type:
        return SummaryNestedResponse(roots=[])

    def tree_to_node(data: dict) -> NestedBreakdownNode:
        return NestedBreakdownNode(
            name=data["name"],
            type_id=data["type_id"],
            quantity=data["quantity"],
            source=data["source"],
            depth=data["depth"],
            children=[tree_to_node(c) for c in data.get("children", [])],
        )

    roots: List[NestedBreakdownNode] = []
    for type_id in sorted(by_type.keys()):
        try:
            eve_type = EveType.objects.get(id=type_id)
        except EveType.DoesNotExist:
            continue
        tree = get_breakdown_for_industry_product(
            eve_type, quantity=by_type[type_id]
        )
        roots.append(tree_to_node(tree))
    return SummaryNestedResponse(roots=roots)
