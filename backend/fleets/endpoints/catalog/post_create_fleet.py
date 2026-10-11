"""POST \"\" — schedule a new fleet."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature

from fleets.helpers.schedule_fleet import (
    create_scheduled_fleet,
    fleet_create_response,
)
from fleets.endpoints.schemas import CreateEveFleetRequest, EveFleetResponse

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
    denied = require_feature(request.user, "fleets.create")
    if denied:
        return denied

    result = create_scheduled_fleet(user=request.user, payload=payload)
    if isinstance(result, tuple):
        return result

    logger.info("Fleet %d created by %s", result.id, request.user.username)
    return fleet_create_response(result)
