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
from industry.helpers.public_short_code import (
    pick_unique_public_short_code_among_actives,
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
        500: ErrorResponse,
    },
}


def _resolve_order_character(request, payload: CreateOrderRequest):
    if payload.character_id is not None:
        character = EveCharacter.objects.filter(
            character_id=payload.character_id, user=request.user
        ).first()
        if not character:
            return None, (
                403,
                ErrorResponse(
                    detail="You may only create orders for your own characters."
                ),
            )
        return character, None
    character = user_primary_character(request.user)
    if not character:
        return None, (
            400,
            ErrorResponse(
                detail="No character specified and no primary character set."
            ),
        )
    return character, None


def _resolve_order_location(payload: CreateOrderRequest):
    if payload.location_id is None:
        return None, None
    try:
        return EveLocation.objects.get(pk=payload.location_id), None
    except EveLocation.DoesNotExist:
        return None, (
            404,
            ErrorResponse(detail=f"Location {payload.location_id} not found."),
        )


def _validate_items_and_eve_types(payload: CreateOrderRequest):
    if not payload.items:
        return None, (
            400,
            ErrorResponse(detail="At least one order item is required."),
        )
    type_ids = [item.eve_type_id for item in payload.items]
    if len(type_ids) != len(set(type_ids)):
        return None, (
            400,
            ErrorResponse(detail="Duplicate eve_type_id in items."),
        )
    for item in payload.items:
        if item.quantity < 1:
            return None, (
                400,
                ErrorResponse(
                    detail=f"Quantity must be positive for type_id {item.eve_type_id}."
                ),
            )
        if (
            item.self_assign_maximum is not None
            and item.self_assign_maximum < 1
        ):
            return None, (
                400,
                ErrorResponse(
                    detail=(
                        "self_assign_maximum must be positive for type_id "
                        f"{item.eve_type_id}."
                    ),
                ),
            )
    eve_types = {t.id: t for t in EveType.objects.filter(id__in=type_ids)}
    missing = [tid for tid in type_ids if tid not in eve_types]
    if missing:
        return None, (
            404,
            ErrorResponse(
                detail=f"Eve type(s) not found: {', '.join(map(str, missing))}."
            ),
        )
    return eve_types, None


def _create_order(
    payload: CreateOrderRequest,
    character,
    location,
    contract_to: str,
):
    order = IndustryOrder.objects.create(
        needed_by=payload.needed_by,
        character=character,
        location=location,
        contract_to=contract_to,
        public_short_code=pick_unique_public_short_code_among_actives(),
    )
    return order, None


def post_order(request, payload: CreateOrderRequest):
    character, err = _resolve_order_character(request, payload)
    if err:
        return err
    location, err = _resolve_order_location(payload)
    if err:
        return err
    eve_types, err = _validate_items_and_eve_types(payload)
    if err:
        return err
    contract_to = (payload.contract_to or "").strip()
    order, err = _create_order(payload, character, location, contract_to)
    if err:
        return err
    for item in payload.items:
        IndustryOrderItem.objects.create(
            order=order,
            eve_type=eve_types[item.eve_type_id],
            quantity=item.quantity,
            self_assign_maximum=item.self_assign_maximum,
        )
    return 201, CreateOrderResponse(
        order_id=order.pk,
        public_short_code=order.public_short_code,
    )
