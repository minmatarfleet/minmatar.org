"""GET /orders/{order_id}/orderitems/{order_item_id}/assignments/breakdown - breakdown per assignment (public)."""

from app.errors import ErrorResponse
from industry.endpoints.breakdown.schemas import (
    AssignmentBreakdownResponse,
    NestedBreakdownNode,
    OrderItemAssignmentsBreakdownResponse,
)
from industry.helpers.type_breakdown import (
    enrich_breakdown_with_industry_product_ids,
    get_breakdown_for_industry_product,
)
from industry.models import IndustryOrder

PATH = "{int:order_id}/orderitems/{int:order_item_id}/assignments/breakdown"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Material breakdown per assignment for an order item",
    "response": {
        200: OrderItemAssignmentsBreakdownResponse,
        404: ErrorResponse,
    },
}


def get_order_item_assignments_breakdown(
    request, order_id: int, order_item_id: int
):
    try:
        order = (
            IndustryOrder.objects.filter(pk=order_id)
            .prefetch_related(
                "items__eve_type",
                "items__assignments__character",
            )
            .get()
        )
    except IndustryOrder.DoesNotExist:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    item = (
        order.items.filter(pk=order_item_id)
        .select_related("eve_type")
        .prefetch_related("assignments__character")
        .first()
    )
    if not item:
        return 404, ErrorResponse(
            detail=f"Order item {order_item_id} not found."
        )
    assignments_list = []
    for assignment in item.assignments.all():
        tree = get_breakdown_for_industry_product(
            item.eve_type, quantity=assignment.quantity
        )
        enrich_breakdown_with_industry_product_ids(tree)
        assignments_list.append(
            AssignmentBreakdownResponse(
                character_id=assignment.character.character_id,
                character_name=assignment.character.character_name,
                quantity=assignment.quantity,
                breakdown=NestedBreakdownNode.from_breakdown_dict(tree),
            )
        )
    return 200, OrderItemAssignmentsBreakdownResponse(
        assignments=assignments_list
    )
