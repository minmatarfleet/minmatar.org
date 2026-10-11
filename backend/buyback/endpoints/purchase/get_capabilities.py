"""GET /stock/purchase-capabilities – current user's hangar-sale rights."""

from authentication import AuthBearer
from buyback.endpoints.schemas import BuybackPurchaseCapabilitiesResponse
from buyback.helpers.auth import can_manage_stock_sales

PATH = "/purchase-capabilities"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Whether the current user can process buyback sales",
    "auth": AuthBearer(),
    "response": {200: BuybackPurchaseCapabilitiesResponse},
}


def get_capabilities(request):
    return BuybackPurchaseCapabilitiesResponse(
        can_manage=can_manage_stock_sales(request.user),
    )
