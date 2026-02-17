import csv
import io
from collections import defaultdict
from datetime import timedelta

from django.http import HttpResponse
from django.utils import timezone
from eveuniverse.models import EveType
from ninja import Router

from industry.helpers.type_breakdown import (
    flatten_nested_breakdown_to_quantities,
    get_breakdown_for_industry_product,
)
from industry.models import IndustryOrder

router = Router(tags=["Industry - Orders Summary"])


@router.get("/tsv")
def get_orders_breakdown_summary_tsv(request):
    """TSV of aggregated flat materials (last 30 days) for copy-paste into Janice."""
    since = timezone.now() - timedelta(days=30)
    orders = IndustryOrder.objects.filter(
        created_at__gte=since
    ).prefetch_related("items__eve_type")
    agg = defaultdict(int)
    for order in orders:
        for item in order.items.all():
            tree = get_breakdown_for_industry_product(
                item.eve_type, quantity=item.quantity
            )
            for type_id, qty in flatten_nested_breakdown_to_quantities(
                tree
            ).items():
                agg[type_id] += qty
    if not agg:
        rows = []
    else:
        types = {t.id: t for t in EveType.objects.filter(id__in=agg.keys())}
        rows = [
            (types[tid].name, agg[tid])
            for tid in sorted(agg.keys(), key=lambda x: -agg[x])
            if tid in types
        ]
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", lineterminator="\n")
    writer.writerow(("name", "quantity"))
    writer.writerows(rows)
    return HttpResponse(
        buf.getvalue(), content_type="text/tab-separated-values; charset=utf-8"
    )
