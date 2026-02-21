"""Deprecated: use GET /api/industry/orders and per-order breakdown endpoints instead."""

from collections import defaultdict
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone
from eveuniverse.models import EveType
from ninja import Router
from pydantic import BaseModel

from industry.helpers.type_breakdown import (
    flatten_nested_breakdown_to_quantities,
    get_breakdown_for_industry_product,
)
from industry.models import IndustryOrder

JANICE_DOCS_URL = "https://janice.e-351.com/api/rest/docs/index.html"

router = Router(tags=["Industry - Orders Summary"])


class SummaryJaniceResponse(BaseModel):
    janice_link: str


def _get_flat_items_last_30_days():
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
        return []
    types = {t.id: t for t in EveType.objects.filter(id__in=agg.keys())}
    return [
        (types[tid].name, agg[tid])
        for tid in sorted(agg.keys(), key=lambda x: -agg[x])
        if tid in types
    ]


@router.get("/janice", response=SummaryJaniceResponse, deprecated=True)
def get_orders_breakdown_summary_janice(request):
    """Submit aggregated flat materials (last 30 days) to Janice pricer; returns link to Janice API docs. Deprecated."""
    items = _get_flat_items_last_30_days()
    api_key = getattr(settings, "JANICE_API_KEY", None) or ""
    api_url = getattr(
        settings,
        "JANICE_API_URL",
        "https://janice.e-351.com/api/rest/v2/pricer",
    )

    payload = "\n".join(f"{name}\t{qty}" for name, qty in items)

    link = JANICE_DOCS_URL
    if api_key and payload:
        try:
            resp = requests.post(
                f"{api_url}?market=2",
                data=payload.encode("utf-8"),
                headers={
                    "Content-Type": "text/plain; charset=utf-8",
                    "X-ApiKey": api_key,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                link = JANICE_DOCS_URL
            if isinstance(data, dict) and data.get("url"):
                link = data["url"]
        except Exception:
            pass

    return SummaryJaniceResponse(janice_link=link)
