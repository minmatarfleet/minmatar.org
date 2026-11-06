"""POST /manage/routes - add a route."""

from django.core.exceptions import ValidationError

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from eveonline.models import EveLocation
from freight.endpoints.manage.common import (
    FIELDS,
    ManageRoute,
    RouteCreateRequest,
    can_manage,
    forbidden,
    route_schema,
)
from freight.models import EveFreightRoute

PATH = "/manage/routes"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Add a freight route",
    "auth": AuthBearer(),
    "response": {
        200: ManageRoute,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_manage_route(request, payload: RouteCreateRequest):
    if not can_manage(request.user):
        return forbidden()
    origin = EveLocation.objects.filter(
        location_id=payload.origin_location_id
    ).first()
    destination = EveLocation.objects.filter(
        location_id=payload.destination_location_id
    ).first()
    if origin is None or destination is None:
        return 404, ErrorResponse.new("Location not found")
    if origin.pk == destination.pk:
        return 400, ErrorResponse.new("Origin and destination must differ")
    if payload.route_type not in EveFreightRoute.RouteType.values:
        return 400, ErrorResponse.new("Unknown route type")
    route = EveFreightRoute(
        origin_location=origin,
        destination_location=destination,
        **{field: getattr(payload, field) for field in FIELDS},
    )
    try:
        route.full_clean()
    except ValidationError as error:
        return 400, ErrorResponse.new("; ".join(error.messages))
    route.save()
    record_change(request.user, f"Freight route added: {route}")
    return 200, route_schema(route)
