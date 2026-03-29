"""DELETE /{fleet_id} — remove a scheduled fleet."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.models import EveFleet

logger = logging.getLogger(__name__)

PATH = "/{fleet_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: None, 403: ErrorResponse},
    "description": "Delete a fleet, must be owner or have fleets.delete_evefleet permission",
}


def delete_fleet(request, fleet_id: int):
    fleet = EveFleet.objects.get(id=fleet_id)
    if request.user != fleet.created_by and not request.user.has_perm(
        "fleets.delete_evefleet"
    ):
        return 403, {
            "detail": "User does not have permission to delete this fleet"
        }
    fleet.delete()
    logger.info("Fleet %d deleted by %s", fleet.id, request.user.username)
    return 200, None
