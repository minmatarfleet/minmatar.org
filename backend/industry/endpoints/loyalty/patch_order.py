"""PATCH /orders/{order_id} - update status, destination, or cancel."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.loyalty.auth_helpers import can_manage_buyback
from industry.endpoints.loyalty.schemas import (
    LoyaltyMarketOrderResponse,
    PatchLoyaltyMarketOrderRequest,
)
from industry.endpoints.loyalty.serialization import market_order_response
from industry.helpers.lp_market_orders import (
    CANCELLED,
    OPEN,
    LpMarketOrderError,
    transition_order,
    update_destination,
    update_order_notes,
)
from industry.models import IndustryLoyaltyPointMarketOrder

PATH = "/orders/{order_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Update a loyalty-point market order status or notes",
    "auth": AuthBearer(),
    "response": {
        200: LoyaltyMarketOrderResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def patch_order(
    request, order_id: int, payload: PatchLoyaltyMarketOrderRequest
):
    order = (
        IndustryLoyaltyPointMarketOrder.objects.select_related(
            "loyalty_point", "created_by", "claimed_by"
        )
        .prefetch_related("claims__claimed_by")
        .filter(pk=order_id)
        .first()
    )
    if not order:
        return 404, ErrorResponse(detail="Order not found.")

    is_manager = can_manage_buyback(request.user)
    is_creator = order.created_by_id == request.user.pk

    if payload.notes is not None:
        if not (is_manager or is_creator):
            return 403, ErrorResponse(detail="feature_denied")
        order = update_order_notes(order, payload.notes)

    new_status = payload.status
    if new_status is not None:
        new_status = new_status.strip().lower()
        can_cancel = (order.status == OPEN and is_creator) or is_manager
        if new_status == CANCELLED:
            if not can_cancel:
                return 403, ErrorResponse(detail="feature_denied")
        elif not is_manager:
            return 403, ErrorResponse(detail="feature_denied")

        try:
            order = transition_order(
                order,
                new_status,
                destination_character_name=payload.destination_character_name,
            )
        except LpMarketOrderError as exc:
            return 400, ErrorResponse(detail=str(exc))
    elif payload.destination_character_name is not None:
        if not is_manager:
            return 403, ErrorResponse(detail="feature_denied")
        order = update_destination(order, payload.destination_character_name)

    order = (
        IndustryLoyaltyPointMarketOrder.objects.select_related(
            "loyalty_point", "created_by", "claimed_by"
        )
        .prefetch_related("claims__claimed_by")
        .get(pk=order.pk)
    )
    return 200, market_order_response(order)
