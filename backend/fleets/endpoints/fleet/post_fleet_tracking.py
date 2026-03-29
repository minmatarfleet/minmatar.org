"""POST /{fleet_id}/tracking — start in-game tracking and Discord ping."""

import logging

from typing import Optional

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.endpoints.schemas import StartFleetRequest
from fleets.models import EveFleet

logger = logging.getLogger(__name__)

PATH = "/{fleet_id}/tracking"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: None, 403: ErrorResponse, 400: ErrorResponse},
    "description": "Start a fleet and send a discord ping, must be the owner of the fleet",
}


def start_fleet(
    request, fleet_id: int, payload: Optional[StartFleetRequest] = None
):
    fleet = EveFleet.objects.get(id=fleet_id)
    if request.user != fleet.created_by:
        return 403, ErrorResponse.log(
            "Not authorized to start this fleet",
            f"User {request.user.username} does not have permission to start tracking fleet {fleet_id}",
        )
    try:
        if payload and payload.fc_character_id:
            fleet.start(payload.fc_character_id)
        else:
            fleet.start(None)
    except Exception as e:
        if "not in a fleet" in str(e):
            return 400, ErrorResponse.log("Not currently in a fleet", e)
        else:
            return 400, ErrorResponse.log(
                f"Error starting fleet {fleet.id}", e
            )

    logger.info("Fleet %d started by %s", fleet.id, request.user.username)
    return 200, None
