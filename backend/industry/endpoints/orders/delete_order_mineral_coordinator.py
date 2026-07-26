"""DELETE /{order_id}/mineral-coordinators/{coordinator_id} — remove volunteer."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.models import IndustryOrder, IndustryOrderMineralCoordinator

PATH = "{int:order_id}/mineral-coordinators/{int:coordinator_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Remove a mineral coordinator from an order",
    "auth": AuthBearer(),
    "response": {
        204: None,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def delete_order_mineral_coordinator(
    request,
    order_id: int,
    coordinator_id: int,
):
    try:
        IndustryOrder.objects.get(pk=order_id)
    except IndustryOrder.DoesNotExist:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")

    coordinator = (
        IndustryOrderMineralCoordinator.objects.select_related("character")
        .filter(pk=coordinator_id, order_id=order_id)
        .first()
    )
    if coordinator is None:
        return 404, ErrorResponse(
            detail=f"Mineral coordinator {coordinator_id} not found."
        )

    if (
        coordinator.character.user_id != request.user.id
        and not request.user.is_staff
    ):
        return 403, ErrorResponse(
            detail="You may only remove your own mineral coordinator signup."
        )

    coordinator.delete()
    return 204, None
