"""add_hub"""

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
    HubCreateRequest,
)

PATH = "/hubs"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Add a market hub (or switch an existing location on)",
    "auth": AuthBearer(),
    "response": {
        200: HubResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
}


def add_hub(request, payload: HubCreateRequest):
    if not allowed(request):
        return forbidden()
    location = EveLocation.objects.filter(
        location_id=payload.location_id
    ).first()
    if location is None:
        if not (
            payload.location_name
            and payload.solar_system_id
            and payload.solar_system_name
        ):
            return 400, ErrorResponse.new(
                "A new location needs a name, solar system id and name"
            )
        location = EveLocation(
            location_id=payload.location_id,
            location_name=payload.location_name,
            short_name=payload.short_name or payload.location_name[:32],
            solar_system_id=payload.solar_system_id,
            solar_system_name=payload.solar_system_name,
            region_id=payload.region_id,
            is_structure=payload.is_structure,
        )
    location.market_active = True
    location.prices_active = True
    location.save()
    record_change(
        request.user,
        f"Market hub added: {location.location_name} "
        f"({location.location_id})",
    )
    return 200, hub_response(location)
