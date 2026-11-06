"""patch_hub"""

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
    HubPatchRequest,
)

PATH = "/hubs/{location_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Set a hub active or switch its order-book sync",
    "auth": AuthBearer(),
    "response": {200: HubResponse, 403: ErrorResponse, 404: ErrorResponse},
}


def patch_hub(request, location_id: int, payload: HubPatchRequest):
    if not allowed(request):
        return forbidden()
    location = EveLocation.objects.filter(location_id=location_id).first()
    if location is None:
        return 404, ErrorResponse.new("Hub not found")
    changes = []
    for field in ("market_active", "prices_active"):
        value = getattr(payload, field)
        if value is not None and value != getattr(location, field):
            setattr(location, field, value)
            changes.append(f"{field}={value}")
    if changes:
        location.save()
        record_change(
            request.user,
            f"Market hub {location.location_name} "
            f"({location.location_id}): {', '.join(changes)}",
        )
    return 200, hub_response(location)
