"""PATCH /{order_id} - edit an industry order.

Pilots may attach or clear the campaign on their own orders. Order managers
(``industry.order.manage``) may also change the deadline, delivery location,
contract recipient and fulfilled state, replacing the Django admin form.
"""

from datetime import date

from django.utils import timezone
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.helpers import resolve_attachable_campaign
from eveonline.models import EveLocation
from groups.helpers.feature_access import can_use_feature
from industry.models import IndustryOrder

ORDER_MANAGE_FEATURE = "industry.order.manage"
MANAGER_FIELDS = {"needed_by", "location_id", "contract_to", "fulfilled"}


class PatchOrderRequest(BaseModel):
    campaign_id: int | None = None
    needed_by: date | None = None
    location_id: int | None = None
    contract_to: str | None = None
    fulfilled: bool | None = None


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


def _apply_changes(order, payload, sent, update_fields):
    """Apply sent fields to the order; return an error tuple or None."""
    if "campaign_id" in sent:
        resolved = resolve_attachable_campaign(payload.campaign_id)
        if isinstance(resolved, tuple):
            return resolved
        order.campaign = resolved
        update_fields.append("campaign")
    if "needed_by" in sent:
        if payload.needed_by is None:
            return 400, ErrorResponse(detail="needed_by cannot be cleared.")
        order.needed_by = payload.needed_by
        update_fields.append("needed_by")
    if "location_id" in sent:
        location = None
        if payload.location_id is not None:
            location = EveLocation.objects.filter(
                pk=payload.location_id
            ).first()
            if location is None:
                return 400, ErrorResponse(
                    detail=f"Location {payload.location_id} not found."
                )
        order.location = location
        update_fields.append("location")
    if "contract_to" in sent:
        order.contract_to = (payload.contract_to or "").strip()[:255]
        update_fields.append("contract_to")
    if "fulfilled" in sent and payload.fulfilled is not None:
        if payload.fulfilled and order.fulfilled_at is None:
            order.fulfilled_at = timezone.now()
            update_fields.append("fulfilled_at")
        elif not payload.fulfilled and order.fulfilled_at is not None:
            order.fulfilled_at = None
            update_fields.append("fulfilled_at")
    return None


def patch_order(request, order_id: int, payload: PatchOrderRequest):
    order = (
        IndustryOrder.objects.filter(pk=order_id)
        .select_related("character")
        .first()
    )
    if order is None:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    is_manager = request.user.is_superuser or can_use_feature(
        request.user, ORDER_MANAGE_FEATURE
    )
    owns = (
        order.character is not None
        and order.character.user_id == request.user.id
    )
    if not owns and not is_manager:
        return 403, ErrorResponse(
            detail="You may only update orders for your own characters."
        )
    sent = payload.model_fields_set
    if sent & MANAGER_FIELDS and not is_manager:
        return 403, ErrorResponse(
            detail="Only order managers can change those fields."
        )

    update_fields = []
    error = _apply_changes(order, payload, sent, update_fields)
    if error:
        return error
    if update_fields:
        order.save(update_fields=update_fields)
    return 200, PatchOrderResponse(id=order.pk)
