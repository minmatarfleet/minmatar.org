"""GET "" - list all industry products with type, strategy, volume, relations.

Producers are loaded separately via GET /products/{id} (lazy on the products page).
"""

from typing import List

from industry.endpoints.products.schemas import (
    IndustryProductListItem,
    IndustryProductRef,
)
from industry.models import IndustryProduct

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List all industry products with strategy, volume, and relations (no producers)",
    "response": {200: List[IndustryProductListItem]},
}


def _refs(products):
    return [
        IndustryProductRef(
            id=p.id, type_id=p.eve_type_id, name=p.eve_type.name
        )
        for p in products
    ]


def get_products(request):
    products = (
        IndustryProduct.objects.select_related("eve_type")
        .prefetch_related("supplied_for__eve_type", "supplies__eve_type")
        .order_by("eve_type__name")
    )
    return [
        IndustryProductListItem(
            id=p.pk,
            type_id=p.eve_type_id,
            name=p.eve_type.name,
            strategy=p.strategy,
            volume=p.volume,
            blueprint_or_reaction_type_id=p.blueprint_or_reaction_type_id,
            supplied_for=_refs(p.supplied_for.all()),
            supplies=_refs(p.supplies.all()),
        )
        for p in products
    ]
