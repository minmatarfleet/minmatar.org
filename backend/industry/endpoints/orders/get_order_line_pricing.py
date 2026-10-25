"""GET /pricing - build-cost floor and Jita prices for a new order line."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveuniverse.models import EveType
from industry.endpoints.orders.schemas import OrderLinePricingResponse
from industry.helpers import order_pricing

PATH = "/pricing"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Amamake build cost and Jita prices for an order line",
    "auth": AuthBearer(),
    "response": {
        200: OrderLinePricingResponse,
        400: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_order_line_pricing(request, type_id: int, quantity: int = 1):
    if quantity < 1:
        return 400, ErrorResponse(detail="Quantity must be positive.")
    if not EveType.objects.filter(id=type_id).exists():
        return 404, ErrorResponse(detail=f"Eve type {type_id} not found.")
    try:
        pricing = order_pricing.line_pricing(type_id, quantity)
    except ValueError as exc:
        return 404, ErrorResponse(detail=str(exc))
    return OrderLinePricingResponse(**pricing.__dict__)
