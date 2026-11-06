"""post_item_expectation"""

from app.errors import ErrorResponse
from audit.helpers import record_change
from authentication import AuthBearer
from eveonline.models import EveLocation
from eveuniverse.models import EveType
from market.models import (
    EveMarketItemExpectation,
)
from market.endpoints.hubs.common import (
    allowed,
    forbidden,
)
from market.endpoints.hubs.schemas import (
    ItemExpectationRequest,
    ItemExpectationRow,
)

PATH = "/hubs/{location_id}/expectations/items"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Track an item on sell orders at a hub",
    "auth": AuthBearer(),
    "response": {
        200: ItemExpectationRow,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_item_expectation(
    request, location_id: int, payload: ItemExpectationRequest
):
    if not allowed(request):
        return forbidden()
    location = EveLocation.objects.filter(location_id=location_id).first()
    eve_type = EveType.objects.filter(id=payload.type_id).first()
    if location is None or eve_type is None:
        return 404, ErrorResponse.new("Hub or item not found")
    EveMarketItemExpectation.objects.update_or_create(
        location=location, item=eve_type, defaults={"quantity": 1}
    )
    record_change(
        request.user,
        f"Item expectation tracked: {eve_type.name} "
        f"at {location.location_name}",
    )
    return 200, ItemExpectationRow(type_id=eve_type.id, name=eve_type.name)
