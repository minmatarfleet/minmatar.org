"""GET /products/{product_id}/breakdown - nested breakdown for an industry product by ID."""

from typing import Optional

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.breakdown.schemas import NestedBreakdownNode
from industry.helpers.type_breakdown import (
    enrich_breakdown_with_industry_product_ids,
    get_breakdown_for_industry_product,
)
from industry.models import IndustryProduct

PATH = "{int:product_id}/breakdown"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Nested material breakdown for an industry product by ID (for collapsing/expanding)",
    "auth": AuthBearer(),
    "response": {
        200: NestedBreakdownNode,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_product_breakdown(
    request,
    product_id: int,
    quantity: int = 1,
    max_depth: Optional[int] = None,
):
    """
    Return the full breakdown for this industry product. Supports quantity and
    max_depth query params so the client can request a truncated tree.
    """
    try:
        product = IndustryProduct.objects.select_related("eve_type").get(
            pk=product_id
        )
    except IndustryProduct.DoesNotExist:
        return 404, ErrorResponse(
            detail=f"Industry product {product_id} not found."
        )
    tree = get_breakdown_for_industry_product(
        product.eve_type,
        quantity=quantity,
        max_depth=max_depth,
    )
    enrich_breakdown_with_industry_product_ids(tree)
    return 200, NestedBreakdownNode.from_breakdown_dict(tree)
