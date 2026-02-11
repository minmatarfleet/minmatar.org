from collections import defaultdict
from datetime import timedelta
from typing import List

from django.utils import timezone
from eveuniverse.models import EveType
from ninja import Router
from pydantic import BaseModel

from industry.helpers.type_breakdown import get_flat_breakdown
from industry.models import IndustryOrder

router = Router(tags=["Industry - Orders Summary"])


class SummaryItem(BaseModel):
    type_id: int
    name: str
    quantity: int


class SummaryFlatResponse(BaseModel):
    items: List[SummaryItem]


@router.get("/flat", response=SummaryFlatResponse)
def get_orders_breakdown_summary_flat(request):
    """Aggregated flat list of base materials for all order items in the last 30 days."""
    since = timezone.now() - timedelta(days=30)
    orders = IndustryOrder.objects.filter(
        created_at__gte=since
    ).prefetch_related("items__eve_type")
    agg: dict[int, int] = defaultdict(int)
    for order in orders:
        for item in order.items.all():
            for eve_type, qty in get_flat_breakdown(
                item.eve_type, quantity=item.quantity
            ):
                agg[eve_type.id] += qty
    if not agg:
        return SummaryFlatResponse(items=[])
    types = {t.id: t for t in EveType.objects.filter(id__in=agg.keys())}
    items = [
        SummaryItem(type_id=tid, name=types[tid].name, quantity=agg[tid])
        for tid in sorted(agg.keys(), key=lambda x: -agg[x])
        if tid in types
    ]
    return SummaryFlatResponse(items=items)
