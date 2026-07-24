"""POST /{order_id}/mineral-coordinators — volunteer to supply minerals."""

from django.db import transaction
from eveuniverse.models import EveType

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveCharacter
from industry.endpoints.orders.schemas import (
    BlueprintCoordinatorResponse,
    BlueprintCoordinatorWriteRequest,
)
from industry.endpoints.orders.serialization import (
    blueprint_coordinator_to_response,
)
from industry.helpers.order_coordinator_materials import (
    validate_mineral_coordinator_eve_type_ids,
)
from industry.models import IndustryOrder, IndustryOrderMineralCoordinator

PATH = "{int:order_id}/mineral-coordinators"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Volunteer as a mineral coordinator for selected minerals on an order",
    "auth": AuthBearer(),
    "response": {
        200: BlueprintCoordinatorResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_order_mineral_coordinator(
    request,
    order_id: int,
    payload: BlueprintCoordinatorWriteRequest,
):
    try:
        character = EveCharacter.objects.get(
            character_id=payload.character_id, user=request.user
        )
    except EveCharacter.DoesNotExist:
        return 403, ErrorResponse(
            detail="You may only volunteer using your own characters."
        )

    with transaction.atomic():
        try:
            order = IndustryOrder.objects.select_for_update().get(pk=order_id)
        except IndustryOrder.DoesNotExist:
            return 404, ErrorResponse(detail=f"Order {order_id} not found.")

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

        coordinator, _ = (
            IndustryOrderMineralCoordinator.objects.update_or_create(
                order=order,
                character=character,
            )
        )
        coordinator.eve_types.set(types)

    coordinator = (
        IndustryOrderMineralCoordinator.objects.select_related("character")
        .prefetch_related("eve_types")
        .get(pk=coordinator.pk)
    )
    return 200, blueprint_coordinator_to_response(coordinator)
