"""GET /products/{product_id} - full detail for one industry product."""

from app.errors import ErrorResponse
from industry.endpoints.products.schemas import (
    CharacterProducerRef,
    CorporationProducerRef,
    IndustryProductDetail,
    IndustryProductRef,
)
from industry.helpers.producers import get_producers_for_types
from industry.models import IndustryProduct

PATH = "{int:product_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Full industry product detail with strategy, volume, relations, character/corp producers",
    "response": {
        200: IndustryProductDetail,
        404: ErrorResponse,
    },
}


def _refs(products):
    return [
        IndustryProductRef(
            id=p.id, type_id=p.eve_type_id, name=p.eve_type.name
        )
        for p in products
    ]


def get_product(request, product_id: int):
    try:
        product = (
            IndustryProduct.objects.filter(pk=product_id)
            .select_related("eve_type")
            .prefetch_related("supplied_for__eve_type", "supplies__eve_type")
            .get()
        )
    except IndustryProduct.DoesNotExist:
        return 404, ErrorResponse(
            detail=f"Industry product {product_id} not found."
        )
    producers = get_producers_for_types([product.eve_type_id])
    by_type = producers.get(product.eve_type_id, {})
    return 200, IndustryProductDetail(
        id=product.pk,
        type_id=product.eve_type_id,
        name=product.eve_type.name,
        strategy=product.strategy,
        volume=product.volume,
        blueprint_or_reaction_type_id=product.blueprint_or_reaction_type_id,
        supplied_for=_refs(product.supplied_for.all()),
        supplies=_refs(product.supplies.all()),
        character_producers=[
            CharacterProducerRef(
                id=c["id"],
                name=c["name"],
                total_value_isk=c.get("total_value_isk", 0.0),
            )
            for c in by_type.get("character_producers", [])
        ],
        corporation_producers=[
            CorporationProducerRef(
                id=c["id"],
                name=c["name"],
                total_value_isk=c.get("total_value_isk", 0.0),
            )
            for c in by_type.get("corporation_producers", [])
        ],
    )
