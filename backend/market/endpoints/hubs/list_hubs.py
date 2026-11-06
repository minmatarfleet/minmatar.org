"""list_hubs"""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveLocation
from market.endpoints.hubs.common import (
    allowed,
    forbidden,
    hub_response,
)
from market.endpoints.hubs.schemas import (
    HubResponse,
)

PATH = "/hubs"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List market hubs",
    "auth": AuthBearer(),
    "response": {200: list[HubResponse], 403: ErrorResponse},
}


def list_hubs(request):
    if not allowed(request):
        return forbidden()
    locations = EveLocation.objects.order_by("location_name")
    return 200, [hub_response(loc) for loc in locations]
