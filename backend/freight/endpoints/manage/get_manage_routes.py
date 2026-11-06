"""GET /manage/routes - every route, retired ones included."""

from django.db.models import Q

from authentication import AuthBearer
from app.errors import ErrorResponse
from eveonline.models import EveLocation
from freight.endpoints.manage.common import (
    ManageRoutes,
    RouteLocation,
    can_manage,
    forbidden,
    route_schema,
)
from freight.models import EveFreightRoute

PATH = "/manage/routes"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Freight routes for the editor",
    "auth": AuthBearer(),
    "response": {200: ManageRoutes, 403: ErrorResponse},
}


def get_manage_routes(request):
    if not can_manage(request.user):
        return forbidden()
    routes = EveFreightRoute.objects.select_related(
        "origin_location", "destination_location"
    ).order_by(
        "origin_location__short_name", "destination_location__short_name"
    )
    return 200, ManageRoutes(
        routes=[route_schema(r) for r in routes],
        locations=[
            RouteLocation(
                location_id=loc.location_id,
                name=loc.location_name,
                short_name=loc.short_name,
            )
            for loc in EveLocation.objects.filter(
                Q(freight_active=True)
            ).order_by("location_name")
        ],
    )
