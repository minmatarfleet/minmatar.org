"""PATCH /{order_id}/mineral-coordinators/{coordinator_id} — update covered minerals."""

from django.db import transaction
from eveuniverse.models import EveType

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.orders.schemas import (
    BlueprintCoordinatorResponse,
    PatchBlueprintCoordinatorRequest,
)
from industry.endpoints.orders.serialization import (
    blueprint_coordinator_to_response,
)
from industry.helpers.order_coordinator_materials import (
    validate_mineral_coordinator_eve_type_ids,
)
from industry.models import IndustryOrder, IndustryOrderMineralCoordinator

PATH = "{int:order_id}/mineral-coordinators/{int:coordinator_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Update the minerals a mineral coordinator covers on an order",
    "auth": AuthBearer(),
    "response": {
        200: BlueprintCoordinatorResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def patch_order_mineral_coordinator(
    request,
    order_id: int,
    coordinator_id: int,
    payload: PatchBlueprintCoordinatorRequest,
):
    with transaction.atomic():
        try:
            order = IndustryOrder.objects.select_for_update().get(pk=order_id)
        except IndustryOrder.DoesNotExist:
            return 404, ErrorResponse(detail=f"Order {order_id} not found.")

        coordinator = (
            IndustryOrderMineralCoordinator.objects.select_for_update()
            .select_related("character")
            .filter(pk=coordinator_id, order=order)
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
                detail="You may only update your own mineral coordinator signup."
            )

        err = validate_mineral_coordinator_eve_type_ids(
            order, payload.eve_type_ids
        )
        if err:
            return 400, ErrorResponse(detail=err)

        types = list(EveType.objects.filter(id__in=payload.eve_type_ids))
        if len(types) != len(set(payload.eve_type_ids)):
            return 400, ErrorResponse(
                detail="One or more Eve types were not found."
            )

        coordinator.eve_types.set(types)

    coordinator = (
        IndustryOrderMineralCoordinator.objects.select_related("character")
        .prefetch_related("eve_types")
        .get(pk=coordinator.pk)
    )
    return 200, blueprint_coordinator_to_response(coordinator)
