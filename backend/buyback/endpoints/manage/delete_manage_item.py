"""DELETE /manage/items/{type_id} - stop accepting a type."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from buyback.endpoints.manage.common import can_manage, forbidden
from buyback.models import BuybackAcceptedItem

PATH = "/manage/items/{type_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Remove an accepted buyback item",
    "auth": AuthBearer(),
    "response": {200: dict, 403: ErrorResponse, 404: ErrorResponse},
}


def delete_manage_item(request, type_id: int):
    if not can_manage(request.user):
        return forbidden()
    item = (
        BuybackAcceptedItem.objects.select_related("eve_type")
        .filter(eve_type_id=type_id)
        .first()
    )
    if item is None:
        return 404, ErrorResponse.new("Item not found")
    name = item.eve_type.name
    item.delete()
    record_change(request.user, f"Buyback item removed: {name}")
    return 200, {"deleted": True}
