"""GET /products/{product_id}/insights - who builds it, demand, stock, losses."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.products.schemas import ProductInsights
from industry.helpers.product_insights import product_insights
from industry.models import IndustryProduct

PATH = "{int:product_id}/insights"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Supply chain insights for an industry product (cached; ready=false while computing)",
    "auth": AuthBearer(),
    "response": {
        200: ProductInsights,
        404: ErrorResponse,
    },
}


def get_product_insights(request, product_id: int):
    if not IndustryProduct.objects.filter(pk=product_id).exists():
        return 404, ErrorResponse(
            detail=f"Industry product {product_id} not found."
        )
    data = product_insights(product_id)
    if data is None:
        return 200, ProductInsights(ready=False)
    return 200, ProductInsights(ready=True, **data)
