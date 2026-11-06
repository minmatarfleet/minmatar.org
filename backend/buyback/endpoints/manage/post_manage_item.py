"""POST /manage/items - accept a new type."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from buyback.endpoints.manage.common import (
    ItemCreateRequest,
    ManageItem,
    can_manage,
    forbidden,
    item_schema,
)
from buyback.models import BuybackAcceptedItem
from eveuniverse.models import EveType

PATH = "/manage/items"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Add an accepted buyback item",
    "auth": AuthBearer(),
    "response": {
        200: ManageItem,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_manage_item(request, payload: ItemCreateRequest):
    if not can_manage(request.user):
        return forbidden()
    if payload.category not in BuybackAcceptedItem.Category.values:
        return 400, ErrorResponse.new("Unknown category")
    eve_type = EveType.objects.filter(id=payload.type_id).first()
    if eve_type is None:
        return 404, ErrorResponse.new("Type not found")
    item, _ = BuybackAcceptedItem.objects.update_or_create(
        eve_type=eve_type,
        defaults={"category": payload.category, "active": True},
    )
    record_change(
        request.user,
        f"Buyback item accepted: {eve_type.name} ({payload.category})",
    )
    return 200, item_schema(item)
