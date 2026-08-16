"""POST "" - create a new industry order."""

import logging

from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter
from eveuniverse.models import EveType

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.orders.schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
)
from industry.helpers.order_submit import (
    ORDER_SUBMIT_FEATURE,
    resolve_staging_location,
    user_can_submit_orders,
    user_must_submit_produced_only,
    validate_needed_by,
    validate_owned_delivery_entity,
    validate_produced_catalog_items,
)
from industry.helpers.public_short_code import (
    pick_unique_public_short_code_among_actives,
)
from industry.models import IndustryOrder, IndustryOrderItem
from industry.tasks import (
    compute_order_profit_breakdown_task,
    emit_order_created_notification,
)

logger = logging.getLogger(__name__)

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
    location, detail = resolve_staging_location(payload.location_id)
    if detail:
        status = 404 if "not found" in detail.lower() else 400
        return None, (status, ErrorResponse(detail=detail))
    return location, None


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


def _validate_produced_only_items(user, eve_types: dict):
    if not user_must_submit_produced_only(user):
        return None
    invalid = validate_produced_catalog_items(list(eve_types.keys()))
    if not invalid:
        return None
    return 400, ErrorResponse(
        detail=(
            "Only produced supply-chain catalog items may be ordered. "
            f"Invalid type_id(s): {', '.join(map(str, invalid))}."
        ),
    )


def _resolve_create_context(request, payload: CreateOrderRequest):
    if not user_can_submit_orders(request.user):
        return None, (
            403,
            {
                "detail": "feature_denied",
                "feature": ORDER_SUBMIT_FEATURE,
            },
        )
    character, err = _resolve_order_character(request, payload)
    if err:
        return None, err
    needed_by_err = validate_needed_by(payload.needed_by)
    if needed_by_err:
        return None, (400, ErrorResponse(detail=needed_by_err))
    location, err = _resolve_order_location(payload)
    if err:
        return None, err
    eve_types, err = _validate_items_and_eve_types(payload)
    if err:
        return None, err
    produced_err = _validate_produced_only_items(request.user, eve_types)
    if produced_err:
        return None, produced_err
    contract_to = (payload.contract_to or "").strip()
    delivery_err = validate_owned_delivery_entity(request.user, contract_to)
    if delivery_err:
        return None, (400, ErrorResponse(detail=delivery_err))
    return {
        "character": character,
        "location": location,
        "eve_types": eve_types,
        "contract_to": contract_to,
    }, None


def _enqueue_post_create_tasks(order_id: int, user_id: int) -> None:
    try:
        compute_order_profit_breakdown_task.delay(order_id)
    except Exception:  # noqa: BLE001 — never fail order create on planner
        logger.exception(
            "Failed to enqueue profit breakdown for order %s", order_id
        )
    try:
        emit_order_created_notification.delay(order_id, user_id)
    except Exception:  # noqa: BLE001 — never fail order create on notify
        logger.exception(
            "Failed to enqueue new-order notification for order %s", order_id
        )


def post_order(request, payload: CreateOrderRequest):
    context, err = _resolve_create_context(request, payload)
    if err:
        return err
    order, err = _create_order(
        payload,
        context["character"],
        context["location"],
        context["contract_to"],
    )
    if err:
        return err
    eve_types = context["eve_types"]
    for item in payload.items:
        IndustryOrderItem.objects.create(
            order=order,
            eve_type=eve_types[item.eve_type_id],
            quantity=item.quantity,
            self_assign_maximum=item.self_assign_maximum,
        )
    _enqueue_post_create_tasks(order.pk, request.user.id)
    return 201, CreateOrderResponse(
        order_id=order.pk,
        public_short_code=order.public_short_code,
    )
