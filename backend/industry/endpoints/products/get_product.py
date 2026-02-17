"""GET /products/{product_id} - full detail for one industry product."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.products.schemas import (
    CharacterProducerRef,
    CorporationProducerRef,
    IndustryProductDetail,
    IndustryProductRef,
)
from industry.helpers.producers import (
    get_character_producers_for_type,
    get_corporation_producers_for_type,
)
from industry.models import IndustryProduct

PATH = "{int:product_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Full industry product detail with strategy, volume, relations, character/corp producers",
    "auth": AuthBearer(),
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
    char_producers = get_character_producers_for_type(product.eve_type_id)
    corp_producers = get_corporation_producers_for_type(product.eve_type_id)
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
            CharacterProducerRef(id=c["id"], name=c["name"])
            for c in char_producers
        ],
        corporation_producers=[
            CorporationProducerRef(id=c["id"], name=c["name"])
            for c in corp_producers
        ],
    )
