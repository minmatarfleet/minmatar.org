"""GET /{order_id} - fetch one order with items and who committed to it (public)."""

from app.errors import ErrorResponse

from industry.endpoints.orders.schemas import (
    OrderDetailResponse,
    OrderLocationResponse,
)
from industry.endpoints.orders.serialization import (
    order_blueprint_coordinators_response,
    order_item_to_response,
    order_lp_stockpiles_response,
    order_mineral_coordinators_response,
    order_pi_coordinators_response,
)
from industry.helpers.order_profit_breakdown import (
    can_refresh_order_profit_breakdown,
)
from industry.models import IndustryOrder

PATH = "{int:order_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get a single order with items and who has committed to each item",
    "response": {
        200: OrderDetailResponse,
        404: ErrorResponse,
    },
}


def get_order(request, order_id: int):
    try:
        order = (
            IndustryOrder.objects.filter(pk=order_id)
            .select_related("character", "location")
            .prefetch_related(
                "items__eve_type",
                "items__assignments__character",
                "blueprint_coordinators__character",
                "blueprint_coordinators__eve_types",
                "mineral_coordinators__character",
                "mineral_coordinators__eve_types",
                "pi_coordinators__character",
                "pi_coordinators__eve_types",
            )
            .get()
        )
    except IndustryOrder.DoesNotExist:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    # Mineral/PI BOM options are expensive (plan_build per line). Load them
    # via GET /orders/{id}/material-options when the coordinators UI needs them.
    return 200, OrderDetailResponse(
        id=order.pk,
        created_at=order.created_at,
        needed_by=order.needed_by,
        fulfilled_at=order.fulfilled_at,
        public_short_code=order.public_short_code,
        contract_to=order.contract_to,
        character_id=order.character.character_id,
        character_name=order.character.character_name,
        location=(
            OrderLocationResponse(
                location_id=order.location.location_id,
                location_name=order.location.location_name,
            )
            if order.location_id
            else None
        ),
        items=[
            order_item_to_response(order, item) for item in order.items.all()
        ],
        lp_stockpiles=order_lp_stockpiles_response(order),
        blueprint_coordinators=order_blueprint_coordinators_response(order),
        mineral_coordinators=order_mineral_coordinators_response(order),
        pi_coordinators=order_pi_coordinators_response(order),
        mineral_options=[],
        pi_options=[],
        profit_breakdown_computed_at=order.profit_breakdown_computed_at,
        can_refresh_profit_breakdown=can_refresh_order_profit_breakdown(order),
    )
