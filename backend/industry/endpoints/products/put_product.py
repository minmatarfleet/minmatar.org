"""PUT "" - create industry product by type_id (and breakdown). Default strategy: import."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveuniverse.models import EveType

from industry.endpoints.products.schemas import (
    IndustryProductListItem,
    PutProductRequest,
)
from industry.helpers.type_breakdown import get_breakdown_for_industry_product
from industry.models import IndustryProduct, IndustryProductStrategy

PATH = ""
METHOD = "put"
ROUTE_SPEC = {
    "summary": "Create industry product for a type_id; compute and store breakdown. Default strategy: import.",
    "auth": AuthBearer(),
    "response": {
        200: IndustryProductListItem,
        404: ErrorResponse,
    },
}


def put_product(request, payload: PutProductRequest):
    """Create or ensure industry product for the given type_id. Default strategy is import."""
    try:
        eve_type, _ = EveType.objects.get_or_create_esi(id=payload.type_id)
    except Exception:
        return 404, ErrorResponse(detail=f"Type {payload.type_id} not found.")
    product, _ = IndustryProduct.objects.get_or_create(
        eve_type=eve_type,
        defaults={"strategy": IndustryProductStrategy.IMPORT},
    )
    get_breakdown_for_industry_product(eve_type, quantity=1, store=True)
    product.refresh_from_db()
    return 200, IndustryProductListItem(
        id=product.pk,
        type_id=product.eve_type_id,
        name=product.eve_type.name,
        strategy=product.strategy,
    )
