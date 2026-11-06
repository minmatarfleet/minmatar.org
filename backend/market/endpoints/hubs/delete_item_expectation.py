"""delete_item_expectation"""

from app.errors import ErrorResponse
from audit.helpers import record_change
from authentication import AuthBearer
from market.models import (
    EveMarketItemExpectation,
)
from market.endpoints.hubs.common import (
    allowed,
    forbidden,
)

PATH = "/hubs/{location_id}/expectations/items/{type_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Stop tracking an item at a hub",
    "auth": AuthBearer(),
    "response": {200: dict, 403: ErrorResponse, 404: ErrorResponse},
}


def delete_item_expectation(request, location_id: int, type_id: int):
    if not allowed(request):
        return forbidden()
    deleted, _ = EveMarketItemExpectation.objects.filter(
        location_id=location_id, item_id=type_id
    ).delete()
    if not deleted:
        return 404, ErrorResponse.new("Expectation not found")
    record_change(
        request.user,
        f"Item expectation removed: type {type_id} at hub {location_id}",
    )
    return 200, {"deleted": deleted}
