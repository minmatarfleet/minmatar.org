"""POST /{fleet_id}/refresh-motd — rebuild in-game MOTD from doctrine/location."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.models import EveFleet, EveFleetInstance

logger = logging.getLogger(__name__)

PATH = "/{fleet_id}/refresh-motd"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: None,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        500: ErrorResponse,
    },
    "description": "Refresh the in-game fleet MOTD from current fleet/doctrine/location. Requires active fleet tracking; caller must be fleet owner.",
}


def refresh_fleet_motd(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, ErrorResponse(detail="Fleet not found")
    if request.user != fleet.created_by:
        return 403, ErrorResponse(
            detail="User does not have permission to refresh MOTD for this fleet"
        )
    instance = EveFleetInstance.objects.filter(
        eve_fleet=fleet, end_time__isnull=True
    ).first()
    if not instance:
        return 400, ErrorResponse(
            detail="No active fleet tracking; start the fleet first to refresh MOTD"
        )
    try:
        instance.refresh_motd()
    except Exception as e:
        logger.exception("Error refreshing MOTD for fleet %d", fleet_id)
        return 500, ErrorResponse.log("Error refreshing MOTD", e)
    return 200, None
