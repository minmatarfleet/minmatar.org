"""POST /{order_id}/blueprint-coordinators — volunteer to supply blueprints."""

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
from industry.helpers.order_lp_stockpiles import (
    validate_coordinator_eve_type_ids,
)
from industry.models import IndustryOrder, IndustryOrderBlueprintCoordinator

PATH = "{int:order_id}/blueprint-coordinators"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Volunteer as a blueprint coordinator for selected ships on an order",
    "auth": AuthBearer(),
    "response": {
        200: BlueprintCoordinatorResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_order_blueprint_coordinator(
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

        err = validate_coordinator_eve_type_ids(order, payload.eve_type_ids)
        if err:
            return 400, ErrorResponse(detail=err)

        types = list(EveType.objects.filter(id__in=payload.eve_type_ids))
        if len(types) != len(set(payload.eve_type_ids)):
            return 400, ErrorResponse(
                detail="One or more Eve types were not found."
            )

        coordinator, _ = (
            IndustryOrderBlueprintCoordinator.objects.update_or_create(
                order=order,
                character=character,
            )
        )
        coordinator.eve_types.set(types)

    coordinator = (
        IndustryOrderBlueprintCoordinator.objects.select_related("character")
        .prefetch_related("eve_types")
        .get(pk=coordinator.pk)
    )
    return 200, blueprint_coordinator_to_response(coordinator)
