"""PATCH .../assignments/{assignment_id} — mark assignment delivered or not."""

from django.db import transaction
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.orders.schemas import (
    AssignmentResponse,
    PatchOrderItemAssignmentRequest,
)
from industry.endpoints.orders.serialization import assignment_to_response
from industry.models import IndustryOrder, IndustryOrderItemAssignment

PATH = "{int:order_id}/orderitems/{int:order_item_id}/assignments/{int:assignment_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Mark an assignment as delivered or not delivered",
    "auth": AuthBearer(),
    "response": {
        200: AssignmentResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def patch_order_item_assignment(
    request,
    order_id: int,
    order_item_id: int,
    assignment_id: int,
    payload: PatchOrderItemAssignmentRequest,
):
    with transaction.atomic():
        try:
            IndustryOrder.objects.select_for_update().get(pk=order_id)
        except IndustryOrder.DoesNotExist:
            return 404, ErrorResponse(detail=f"Order {order_id} not found.")

        assignment = (
            IndustryOrderItemAssignment.objects.select_for_update()
            .filter(
                pk=assignment_id,
                order_item_id=order_item_id,
                order_item__order_id=order_id,
            )
            .select_related("character", "order_item__order__character")
            .first()
        )
        if not assignment:
            return 404, ErrorResponse(detail="Assignment not found.")

        order = assignment.order_item.order
        owner_uid = order.character.user_id
        assignee_uid = assignment.character.user_id
        if request.user.id not in (owner_uid, assignee_uid):
            return 403, ErrorResponse(
                detail="Only the order owner or the assignee may update delivery status."
            )

        if payload.delivered:
            assignment.delivered_at = timezone.now()
        else:
            assignment.delivered_at = None
        assignment.save(update_fields=["delivered_at"])

    assignment = IndustryOrderItemAssignment.objects.select_related(
        "character"
    ).get(pk=assignment.pk)
    return 200, assignment_to_response(assignment)
