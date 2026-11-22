"""GET /v2/locations — staging locations for fleet form-up."""

from typing import List

from django.db.models import Count

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveLocation

from fleets.endpoints.schemas import EveFleetLocationResponse
from fleets.helpers.fleet_form_access import fleet_form_denied

PATH = "/v2/locations"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetLocationResponse], 403: ErrorResponse},
    "description": (
        "Form-up locations for the fleet form. Needs fleets.create, or the "
        "right to schedule fleets for a tribe group."
    ),
}


def get_v2_fleet_locations(request):
    denied = fleet_form_denied(request.user)
    if denied:
        return denied
    response = []
    locations = (
        EveLocation.objects.all()
        .filter(fleets_active=True)
        .annotate(count=Count("evefleet__id"))
        .order_by("-count", "location_name")
    )
    for location in locations:
        response.append(
            {
                "location_id": location.location_id,
                "location_name": location.location_name,
                "solar_system_id": location.solar_system_id,
                "solar_system_name": location.solar_system_name,
                "short_name": location.short_name,
                "staging_active": location.staging_active,
                "deployment_active": location.deployment_active,
            }
        )
    return response
