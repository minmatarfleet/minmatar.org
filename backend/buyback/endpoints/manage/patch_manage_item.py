"""PATCH /manage/items/{type_id} - re-categorise or switch an item off."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from buyback.endpoints.manage.common import (
    ItemPatchRequest,
    ManageItem,
    can_manage,
    forbidden,
    item_schema,
)
from buyback.models import BuybackAcceptedItem

PATH = "/manage/items/{type_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Edit an accepted buyback item",
    "auth": AuthBearer(),
    "response": {
        200: ManageItem,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def patch_manage_item(request, type_id: int, payload: ItemPatchRequest):
    if not can_manage(request.user):
        return forbidden()
    item = (
        BuybackAcceptedItem.objects.select_related("eve_type")
        .filter(eve_type_id=type_id)
        .first()
    )
    if item is None:
        return 404, ErrorResponse.new("Item not found")
    if (
        payload.category is not None
        and payload.category not in BuybackAcceptedItem.Category.values
    ):
        return 400, ErrorResponse.new("Unknown category")
    changes = []
    for field in ("active", "category"):
        value = getattr(payload, field)
        if value is not None and value != getattr(item, field):
            changes.append(f"{field} {getattr(item, field)} -> {value}")
            setattr(item, field, value)
    if changes:
        item.save()
        record_change(
            request.user,
            f"Buyback item {item.eve_type.name}: " + "; ".join(changes),
        )
    return 200, item_schema(item)
