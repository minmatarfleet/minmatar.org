"""GET "" - list all industry products with type, strategy, volume, relations, producers."""

from typing import List

from authentication import AuthBearer

from industry.endpoints.products.schemas import (
    CharacterProducerRef,
    CorporationProducerRef,
    IndustryProductListItem,
    IndustryProductRef,
    PlanetaryProducerRef,
)
from industry.helpers.producers import get_producers_for_types
from industry.models import IndustryProduct

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List all industry products with strategy, volume, relations, character/corp producers",
    "auth": AuthBearer(),
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
    type_ids = [p.eve_type_id for p in products]
    producers_by_type = get_producers_for_types(type_ids)
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
            character_producers=[
                CharacterProducerRef(id=c["id"], name=c["name"])
                for c in producers_by_type.get(p.eve_type_id, {}).get(
                    "character_producers", []
                )
            ],
            corporation_producers=[
                CorporationProducerRef(id=c["id"], name=c["name"])
                for c in producers_by_type.get(p.eve_type_id, {}).get(
                    "corporation_producers", []
                )
            ],
            planetary_producers=[
                PlanetaryProducerRef(**pp)
                for pp in producers_by_type.get(p.eve_type_id, {}).get(
                    "planetary_producers", []
                )
            ],
        )
        for p in products
    ]
