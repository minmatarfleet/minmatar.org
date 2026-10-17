"""POST /{fleet_id}/missing-signups/nudge — DM signed-up pilots not in fleet."""

from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.endpoints.helpers import _fleet_manager
from fleets.helpers.missing_signups import (
    claim_nudge,
    live_instance,
    missing_signups,
)
from fleets.models import EveFleet
from fleets.tasks import nudge_missing_signups

PATH = "/{fleet_id}/missing-signups/nudge"
METHOD = "post"


class NudgeQueuedResponse(BaseModel):
    pilots: int


ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        202: NudgeQueuedResponse,
        400: ErrorResponse,
        403: None,
        404: None,
        429: ErrorResponse,
    },
    "description": (
        "Queue one Discord DM per player whose signed-up characters are not "
        "in the live fleet. Allowed once per fleet every 15 minutes."
    ),
}


def nudge_fleet_missing_signups(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_manager(request, fleet):
        return 403, None
    if not live_instance(fleet):
        return 400, ErrorResponse(detail="Fleet is not being tracked")
    pilots = missing_signups(fleet)
    if not pilots:
        return 400, ErrorResponse(detail="Everyone who signed up is in fleet")
    if not claim_nudge(fleet.id):
        return 429, ErrorResponse(detail="Nudged recently; try again later")
    nudge_missing_signups.delay(fleet.id)
    return 202, NudgeQueuedResponse(pilots=len(pilots))
