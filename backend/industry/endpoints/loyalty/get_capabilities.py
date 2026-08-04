"""GET /capabilities - current user's LP buyback capabilities."""

from authentication import AuthBearer
from groups.helpers.feature_access import can_use_feature
from industry.endpoints.loyalty.auth_helpers import can_manage_buyback
from industry.endpoints.loyalty.schemas import LoyaltyCapabilitiesResponse

PATH = "/capabilities"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Loyalty buyback capabilities for the current user",
    "auth": AuthBearer(),
    "response": {200: LoyaltyCapabilitiesResponse},
}


def get_capabilities(request):
    return LoyaltyCapabilitiesResponse(
        can_manage=can_manage_buyback(request.user),
        can_trade=can_use_feature(request.user, "industry.loyalty.trade")
        or request.user.is_staff,
    )
