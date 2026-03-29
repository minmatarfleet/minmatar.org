"""POST \"\" — schedule a new fleet."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveLocation
from fittings.models import EveDoctrine

from fleets.endpoints.helpers import send_discord_pre_ping
from fleets.endpoints.schemas import CreateEveFleetRequest, EveFleetResponse
from fleets.models import EveFleet, EveFleetAudience

logger = logging.getLogger(__name__)

PATH = ""
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetResponse,
        403: ErrorResponse,
        400: ErrorResponse,
    },
    "description": "Create a new fleet, type/location/audience is from other endpoints. Must have fleets.add_evefleet permission",
}


def create_fleet(request, payload: CreateEveFleetRequest):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}

    if not EveFleetAudience.objects.filter(id=payload.audience_id).exists():
        return 400, {"detail": "Audience does not exist"}

    audience = EveFleetAudience.objects.get(id=payload.audience_id)

    location = None
    if payload.location_id:
        if not EveLocation.objects.filter(
            location_id=payload.location_id
        ).exists():
            return 400, {"detail": "Location does not exist"}
        location = EveLocation.objects.get(location_id=payload.location_id)
    elif audience.staging_location:
        location = audience.staging_location

    fleet = EveFleet.objects.create(
        type=payload.type,
        description=payload.description,
        objective=(payload.objective or "").strip(),
        start_time=payload.start_time,
        created_by=request.user,
        location=location,
        audience=audience,
        disable_motd=payload.disable_motd,
        status="pending",
    )

    if payload.doctrine_id:
        doctrine = EveDoctrine.objects.get(id=payload.doctrine_id)
        fleet.doctrine = doctrine
        fleet.save()

    if not fleet.audience.add_to_schedule:
        payload.immediate_ping = True

    if payload.immediate_ping:
        send_discord_pre_ping(fleet)

    out = {
        "id": fleet.id,
        "type": fleet.type,
        "description": fleet.description,
        "objective": fleet.objective or None,
        "start_time": fleet.start_time,
        "fleet_commander": fleet.created_by.id,
        "location": (
            fleet.formup_location.location_name
            if fleet.formup_location
            else "Ask FC"
        ),
        "audience": fleet.audience.name,
        "disable_motd": fleet.disable_motd,
        "status": fleet.status,
    }

    if fleet.doctrine:
        out["doctrine_id"] = fleet.doctrine.id

    logger.info("Fleet %d created by %s", fleet.id, request.user.username)

    return EveFleetResponse(**out)
