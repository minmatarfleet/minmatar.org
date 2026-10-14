"""PATCH /{order_id} - attach or clear the campaign on an industry order."""

from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.helpers import resolve_attachable_campaign
from industry.models import IndustryOrder


class PatchOrderRequest(BaseModel):
    campaign_id: int | None = None


class PatchOrderResponse(BaseModel):
    id: int


PATH = "{int:order_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Attach or clear the campaign on an industry order.",
    "auth": AuthBearer(),
    "response": {
        200: PatchOrderResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def patch_order(request, order_id: int, payload: PatchOrderRequest):
    order = (
        IndustryOrder.objects.filter(pk=order_id)
        .select_related("character")
        .first()
    )
    if order is None:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    owns = (
        order.character is not None
        and order.character.user_id == request.user.id
    )
    if not owns and not request.user.is_superuser:
        return 403, ErrorResponse(
            detail="You may only update orders for your own characters."
        )
    if "campaign_id" in payload.model_fields_set:
        resolved = resolve_attachable_campaign(payload.campaign_id)
        if isinstance(resolved, tuple):
            return resolved
        order.campaign = resolved
        order.save(update_fields=["campaign"])
    return 200, PatchOrderResponse(id=order.pk)
