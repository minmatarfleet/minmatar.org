"""GET /capabilities - manufacturing order submit capabilities."""

from authentication import AuthBearer
from industry.endpoints.orders.schemas import OrderCapabilitiesResponse
from industry.helpers.order_submit import order_submit_capabilities

PATH = "/capabilities"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Manufacturing order submit capabilities for the current user",
    "auth": AuthBearer(),
    "response": {200: OrderCapabilitiesResponse},
}


def get_order_capabilities(request):
    caps = order_submit_capabilities(request.user)
    return OrderCapabilitiesResponse(
        can_submit=caps["can_submit"],
        produced_only=caps["produced_only"],
    )
