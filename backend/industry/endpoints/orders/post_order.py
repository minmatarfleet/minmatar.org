"""POST "" - create a new industry order."""

from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter, EveLocation
from eveuniverse.models import EveType

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.orders.schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
)
from industry.models import IndustryOrder, IndustryOrderItem

PATH = ""
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Create a new industry order for the authenticated user's character",
    "auth": AuthBearer(),
    "response": {
        201: CreateOrderResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_order(request, payload: CreateOrderRequest):
    character = None
    if payload.character_id is not None:
        character = EveCharacter.objects.filter(
            character_id=payload.character_id, user=request.user
        ).first()
        if not character:
            return 403, ErrorResponse(
                detail="You may only create orders for your own characters."
            )
    else:
        character = user_primary_character(request.user)
        if not character:
            return 400, ErrorResponse(
                detail="No character specified and no primary character set."
            )

    if not payload.items:
        return 400, ErrorResponse(
            detail="At least one order item is required."
        )

    location = None
    if payload.location_id is not None:
        try:
            location = EveLocation.objects.get(pk=payload.location_id)
        except EveLocation.DoesNotExist:
            return 404, ErrorResponse(
                detail=f"Location {payload.location_id} not found."
            )

    type_ids = [item.eve_type_id for item in payload.items]
    if len(type_ids) != len(set(type_ids)):
        return 400, ErrorResponse(detail="Duplicate eve_type_id in items.")
    eve_types = {t.id: t for t in EveType.objects.filter(id__in=type_ids)}
    missing = [tid for tid in type_ids if tid not in eve_types]
    if missing:
        return 404, ErrorResponse(
            detail=f"Eve type(s) not found: {', '.join(map(str, missing))}."
        )
    for item in payload.items:
        if item.quantity < 1:
            return 400, ErrorResponse(
                detail=f"Quantity must be positive for type_id {item.eve_type_id}."
            )

    order = IndustryOrder.objects.create(
        needed_by=payload.needed_by,
        character=character,
        location=location,
    )
    for item in payload.items:
        IndustryOrderItem.objects.create(
            order=order,
            eve_type=eve_types[item.eve_type_id],
            quantity=item.quantity,
        )
    return 201, CreateOrderResponse(order_id=order.pk)
