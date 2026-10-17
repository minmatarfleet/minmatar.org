"""GET /{fleet_id}/missing-signups — signed-up pilots not in the live fleet."""

from typing import List, Optional

from pydantic import BaseModel

from authentication import AuthBearer
from fleets.endpoints.helpers import _fleet_manager
from fleets.helpers.missing_signups import missing_signups, nudge_state
from fleets.models import EveFleet

PATH = "/{fleet_id}/missing-signups"
METHOD = "get"


class MissingSignupPilot(BaseModel):
    character_id: int
    character_name: str
    ship_name: str
    cyno: bool


class NudgeResult(BaseModel):
    sent_at: str
    players: int
    delivered: int
    failed: int


class MissingSignupsResponse(BaseModel):
    pilots: List[MissingSignupPilot]
    last_nudge: Optional[NudgeResult] = None
    next_nudge_at: Optional[str] = None


ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: MissingSignupsResponse, 403: None, 404: None},
    "description": (
        "FC and fleet managers: ship volunteers whose character is not in the "
        "live fleet, plus the last DM nudge and when the next one is allowed. "
        "Empty when the fleet is not being tracked."
    ),
}


def get_fleet_missing_signups(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_manager(request, fleet):
        return 403, None
    state = nudge_state(fleet.id)
    next_at = state["next_allowed_at"]
    return MissingSignupsResponse(
        pilots=missing_signups(fleet),
        last_nudge=state["last"],
        next_nudge_at=next_at.isoformat() if next_at else None,
    )
