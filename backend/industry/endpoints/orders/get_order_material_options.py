"""GET /{order_id}/material-options — mineral/PI checkbox lists (public)."""

from app.errors import ErrorResponse
from industry.endpoints.orders.schemas import OrderMaterialOptionsResponse
from industry.endpoints.orders.serialization import (
    coordinator_eve_types_response,
)
from industry.helpers.order_coordinator_materials import (
    order_mineral_and_pi_options,
)
from industry.models import IndustryOrder

PATH = "{int:order_id}/material-options"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "Mineral and PI supply options for coordinators "
        "(basic minerals + navy-hull PI; not order BOM)"
    ),
    "response": {
        200: OrderMaterialOptionsResponse,
        404: ErrorResponse,
    },
}


def get_order_material_options(request, order_id: int):
    if not IndustryOrder.objects.filter(pk=order_id).exists():
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    mineral_types, pi_types = order_mineral_and_pi_options()
    return 200, OrderMaterialOptionsResponse(
        mineral_options=coordinator_eve_types_response(mineral_types),
        pi_options=coordinator_eve_types_response(pi_types),
    )
