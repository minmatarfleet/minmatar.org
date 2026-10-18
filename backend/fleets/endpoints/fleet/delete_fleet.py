"""DELETE /{fleet_id} — remove a scheduled fleet."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import can_use_feature

from fleets.helpers.removal import remove_fleet
from fleets.models import EveFleet, close_fleet_cleanup

logger = logging.getLogger(__name__)

PATH = "/{fleet_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: None, 403: ErrorResponse},
    "description": (
        "Delete a fleet, must be owner or have fleets.delete_evefleet "
        "permission. A fleet with attendance or SRP claims is cancelled "
        "instead, so its history is kept."
    ),
}


def delete_fleet(request, fleet_id: int):
    fleet = EveFleet.objects.get(id=fleet_id)
    if request.user != fleet.created_by and not can_use_feature(
        request.user, "fleets.delete"
    ):
        return 403, {
            "detail": "User does not have permission to delete this fleet"
        }
    fleet_id = fleet.id
    close_fleet_cleanup(fleet)
    outcome = remove_fleet(fleet)
    logger.info("Fleet %d %s by %s", fleet_id, outcome, request.user.username)
    return 200, None
