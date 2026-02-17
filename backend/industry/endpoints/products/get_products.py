"""GET "" - list all industry products with type and strategy (import/export/integrated)."""

from typing import List

from authentication import AuthBearer

from industry.endpoints.products.schemas import IndustryProductListItem
from industry.models import IndustryProduct

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List all industry products and whether we import, export, or use them in production",
    "auth": AuthBearer(),
    "response": {200: List[IndustryProductListItem]},
}


def get_products(request):
    products = IndustryProduct.objects.select_related("eve_type").order_by(
        "eve_type__name"
    )
    return [
        IndustryProductListItem(
            id=p.pk,
            type_id=p.eve_type_id,
            name=p.eve_type.name,
            strategy=p.strategy,
        )
        for p in products
    ]
