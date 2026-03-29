"""PATCH /{fleet_id} — update scheduled fleet (FC / privileged)."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.endpoints.helpers import (
    _fleet_apply_optional_scalar_updates,
    _fleet_patch_audience_location_errors,
    update_instance_endtime,
)
from fleets.endpoints.schemas import EveFleetResponse, UpdateEveFleetRequest
from fleets.models import EveFleet

logger = logging.getLogger(__name__)

PATH = "/{fleet_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetResponse,
        403: ErrorResponse,
        400: ErrorResponse,
    },
    "description": "Update the fleet details. Must have fleets.add_evefleet permission",
}


def update_fleet(request, fleet_id: int, payload: UpdateEveFleetRequest):
    if not (
        request.user.is_superuser
        or request.user.has_perm("fleets.add_evefleet")
    ):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}

    fleet = EveFleet.objects.get(id=fleet_id)

    err = _fleet_patch_audience_location_errors(fleet, payload)
    if err:
        return 400, err
    _fleet_apply_optional_scalar_updates(fleet, payload)

    fleet.save()

    if payload.status and (payload.status == "complete"):
        update_instance_endtime(fleet)

    out = {
        "id": fleet.id,
        "type": fleet.type,
        "description": fleet.description,
        "objective": fleet.objective or None,
        "start_time": fleet.start_time,
        "fleet_commander": fleet.created_by.id if fleet.created_by else None,
        "location": (
            fleet.formup_location.location_name
            if fleet.formup_location
            else None
        ),
        "audience": fleet.audience.name if fleet.audience else None,
        "doctrine_id": fleet.doctrine.id if fleet.doctrine else None,
        "status": fleet.status,
        "disable_motd": fleet.disable_motd,
        "aar_link": fleet.aar_link,
    }

    return EveFleetResponse(**out)
