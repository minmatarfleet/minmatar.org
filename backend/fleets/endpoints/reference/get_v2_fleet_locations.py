"""GET /v2/locations — staging locations for fleet form-up."""

from typing import List

from django.db.models import Count

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveLocation

from fleets.endpoints.schemas import EveFleetLocationResponse

PATH = "/v2/locations"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetLocationResponse], 403: ErrorResponse},
}


def get_v2_fleet_locations(request):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}
    response = []
    locations = (
        EveLocation.objects.all()
        .filter(staging_active=True)
        .annotate(count=Count("evefleet__id"))
        .order_by("-count")
    )
    for location in locations:
        response.append(
            {
                "location_id": location.location_id,
                "location_name": location.location_name,
                "solar_system_id": location.solar_system_id,
                "solar_system_name": location.solar_system_name,
            }
        )
    return response
