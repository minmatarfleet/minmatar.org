"""POST /manage/items - accept a new type."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from buyback.endpoints.manage.common import (
    ItemCreateRequest,
    ManageItem,
    can_manage,
    forbidden,
    infer_category,
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
    if (
        payload.category
        and payload.category not in BuybackAcceptedItem.Category.values
    ):
        return 400, ErrorResponse.new("Unknown category")
    eve_type = (
        EveType.objects.select_related("eve_group")
        .filter(id=payload.type_id)
        .first()
    )
    if eve_type is None:
        return 404, ErrorResponse.new("Type not found")
    category = payload.category or infer_category(eve_type)
    if not category:
        return 400, ErrorResponse.new(
            f"{eve_type.name} is not ore or a planetary commodity: "
            "pick its category"
        )
    item, _ = BuybackAcceptedItem.objects.update_or_create(
        eve_type=eve_type,
        defaults={"category": category, "active": True},
    )
    record_change(
        request.user,
        f"Buyback item accepted: {eve_type.name} ({category})",
    )
    return 200, item_schema(item)
