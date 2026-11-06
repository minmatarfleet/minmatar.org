"""remove_hub"""

from app.errors import ErrorResponse
from audit.helpers import record_change
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

PATH = "/hubs/{location_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Remove a hub from the market",
    "description": (
        "Switches the alliance market off. The location and its "
        "expectations stay, so the hub can be added back. The price "
        "baseline keeps syncing its order book."
    ),
    "auth": AuthBearer(),
    "response": {200: HubResponse, 403: ErrorResponse, 404: ErrorResponse},
}


def remove_hub(request, location_id: int):
    if not allowed(request):
        return forbidden()
    location = EveLocation.objects.filter(location_id=location_id).first()
    if location is None:
        return 404, ErrorResponse.new("Hub not found")
    location.market_active = False
    # Jita is often the price baseline and not an alliance market hub.
    # Removing it from the hub list must not stop live baseline prices.
    if not location.price_baseline:
        location.prices_active = False
    location.save()
    record_change(
        request.user,
        f"Market hub removed: {location.location_name} "
        f"({location.location_id})",
    )
    return 200, hub_response(location)
