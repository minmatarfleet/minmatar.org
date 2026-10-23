"""POST /{fleet_id}/copy — schedule a copy of a fleet on a new date."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.endpoints.helpers import _fleet_authorized
from fleets.endpoints.schemas import CopyEveFleetRequest, EveFleetCopyResponse
from fleets.helpers.copy_fleet import copy_fleet
from fleets.helpers.schedule_fleet import fleet_create_response
from fleets.models import EveFleet

logger = logging.getLogger(__name__)

PATH = "/{fleet_id}/copy"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetCopyResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: None,
    },
    "description": (
        "Schedule a new fleet at start_time with this fleet's settings: "
        "host, type, objective, briefing, staging, doctrine, campaign, the "
        "ships the FC added and their refits, hide names and MOTD. The "
        "caller becomes its FC; sign-ups start empty. Must manage the fleet "
        "and be able to schedule fleets for its host. A campaign that has "
        "ended by then, a staging that is no longer active and an open flag "
        "the group no longer allows are left off and listed in not_copied."
    ),
}


def copy_fleet_to_date(request, fleet_id: int, payload: CopyEveFleetRequest):
    source = EveFleet.objects.filter(id=fleet_id).first()
    if not source:
        return 404, None
    if not _fleet_authorized(request, source):
        return 403, ErrorResponse.new("You can't see this fleet")

    result = copy_fleet(
        user=request.user, source=source, start_time=payload.start_time
    )
    if isinstance(result, tuple):
        return result

    logger.info(
        "Fleet %d copied to fleet %d by %s",
        source.id,
        result.fleet.id,
        request.user.username,
    )
    created = fleet_create_response(result.fleet)
    return EveFleetCopyResponse(
        **created.model_dump(),
        copied_from=source.id,
        not_copied=result.not_copied,
    )
