"""PATCH /manage/routes/{id} - edit pricing or retire a route."""

from django.core.exceptions import ValidationError

from app.errors import ErrorResponse
from audit.helpers import record_change
from authentication import AuthBearer
from freight.endpoints.manage.common import (
    FIELDS,
    NULLABLE_FIELDS,
    ManageRoute,
    RoutePatchRequest,
    can_manage,
    forbidden,
    route_schema,
)
from freight.models import EveFreightRoute

PATH = "/manage/routes/{route_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Edit or retire a freight route",
    "auth": AuthBearer(),
    "response": {
        200: ManageRoute,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def patch_manage_route(request, route_id: int, payload: RoutePatchRequest):
    if not can_manage(request.user):
        return forbidden()
    route = (
        EveFreightRoute.objects.select_related(
            "origin_location", "destination_location"
        )
        .filter(pk=route_id)
        .first()
    )
    if route is None:
        return 404, ErrorResponse.new("Route not found")
    if (
        payload.route_type is not None
        and payload.route_type not in EveFreightRoute.RouteType.values
    ):
        return 400, ErrorResponse.new("Unknown route type")
    changes = []
    sent = payload.model_fields_set
    for field in FIELDS:
        if field not in sent:
            continue
        value = getattr(payload, field)
        # Null means "leave it" except for the caps, which an empty box clears.
        if value is None and field not in NULLABLE_FIELDS:
            continue
        if value != getattr(route, field):
            changes.append(f"{field} {getattr(route, field)} -> {value}")
            setattr(route, field, value)
    if not changes:
        return 200, route_schema(route)
    try:
        route.full_clean()
    except ValidationError as error:
        return 400, ErrorResponse.new("; ".join(error.messages))
    route.save()
    record_change(
        request.user, f"Freight route {route}: " + "; ".join(changes)
    )
    return 200, route_schema(route)
