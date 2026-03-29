"""GET /{fleet_id} — fleet detail for authorized viewers."""

from authentication import AuthBearer

from fleets.endpoints.schemas import EveFleetResponse, EveFleetTrackingResponse
from fleets.models import EveFleet, EveFleetInstance

PATH = "/{fleet_id}"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: EveFleetResponse, 403: None, 404: None},
    "description": "Get fleet by ID. Requires fleets.view_evefleet.",
}


def get_fleet(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not request.user.has_perm("fleets.view_evefleet"):
        return 403, None

    tracking = None
    if EveFleetInstance.objects.filter(eve_fleet=fleet).exists():
        tracking = EveFleetTrackingResponse.model_validate(
            EveFleetInstance.objects.get(eve_fleet=fleet)
        )

    payload = {
        "id": fleet.id,
        "type": fleet.type,
        "description": fleet.description,
        "objective": fleet.objective or None,
        "start_time": fleet.start_time,
        "fleet_commander": fleet.created_by.id if fleet.created_by else 0,
        "location": (
            fleet.formup_location.location_name
            if fleet.formup_location
            else "Ask FC"
        ),
        "audience": fleet.audience.name,
        "tracking": tracking,
        "disable_motd": fleet.disable_motd,
        "status": fleet.status,
        "aar_link": fleet.aar_link,
    }
    if fleet.doctrine:
        payload["doctrine_id"] = fleet.doctrine.id

    return EveFleetResponse(**payload)
