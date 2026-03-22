"""POST /{order_id}/orderitems/{order_item_id}/assignments — assign quantity to user's character."""

from django.db import transaction
from django.db.models import Sum

from eveonline.models import EveCharacter

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.orders.schemas import (
    AssignmentResponse,
    PostOrderItemAssignmentRequest,
)
from industry.endpoints.orders.serialization import assignment_to_response
from industry.helpers.order_assignments import validate_assignment_quantity
from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)

PATH = "{int:order_id}/orderitems/{int:order_item_id}/assignments"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Assign part of an order line to one of your characters",
    "auth": AuthBearer(),
    "response": {
        201: AssignmentResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_order_item_assignment(
    request,
    order_id: int,
    order_item_id: int,
    payload: PostOrderItemAssignmentRequest,
):
    try:
        character = EveCharacter.objects.get(
            character_id=payload.character_id, user=request.user
        )
    except EveCharacter.DoesNotExist:
        return 403, ErrorResponse(
            detail="You may only assign using your own characters."
        )

    with transaction.atomic():
        try:
            IndustryOrder.objects.select_for_update().get(pk=order_id)
        except IndustryOrder.DoesNotExist:
            return 404, ErrorResponse(detail=f"Order {order_id} not found.")

        item = (
            IndustryOrderItem.objects.select_for_update()
            .filter(pk=order_item_id, order_id=order_id)
            .select_related("order")
            .first()
        )
        if not item:
            return 404, ErrorResponse(
                detail=f"Order item {order_item_id} not found on this order."
            )
        order = item.order

        totals = IndustryOrderItemAssignment.objects.filter(
            order_item=item
        ).aggregate(total=Sum("quantity"))
        total_assigned = totals["total"] or 0

        char_totals = IndustryOrderItemAssignment.objects.filter(
            order_item=item, character=character
        ).aggregate(t=Sum("quantity"))
        qty_for_char = char_totals["t"] or 0

        err = validate_assignment_quantity(
            line_quantity=item.quantity,
            self_assign_maximum=item.self_assign_maximum,
            total_assigned=total_assigned,
            quantity_for_character=qty_for_char,
            add_quantity=payload.quantity,
            order=order,
        )
        if err:
            return 400, ErrorResponse(detail=err)

        assignment, created = (
            IndustryOrderItemAssignment.objects.get_or_create(
                order_item=item,
                character=character,
                defaults={"quantity": payload.quantity},
            )
        )
        if not created:
            assignment.quantity += payload.quantity
            assignment.save(update_fields=["quantity"])

    assignment = IndustryOrderItemAssignment.objects.select_related(
        "character"
    ).get(pk=assignment.pk)
    return 201, assignment_to_response(assignment)
