"""GET /{fleet_id}/mining — ore mined per pilot (docs/fleets/mining-tracking.md)."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

from authentication import AuthBearer
from eveonline.helpers.characters import user_characters
from fleets.endpoints.helpers import _fleet_authorized, sees_all_volunteers
from fleets.helpers.mining import fleet_mining_results, fleet_mining_timeline
from fleets.models import EveFleet

PATH = "/{fleet_id}/mining"
METHOD = "get"


class FleetMiningOre(BaseModel):
    type_id: int
    name: str
    quantity: int
    volume_m3: float
    isk_estimate: float


class FleetMiningPilot(BaseModel):
    # Null for a pilot the viewer may not name (the fleet hides its roster).
    character_id: Optional[int] = None
    character_name: Optional[str] = None
    status: Literal["measuring", "done", "partial", "no_scope"]
    ores: List[FleetMiningOre]
    volume_m3: float
    isk_estimate: float


class FleetMiningTimelinePilot(BaseModel):
    character_id: Optional[int] = None
    character_name: Optional[str] = None
    no_scope: bool
    # One per bucket: ore, quiet (in fleet, nothing seen yet), idle (in
    # fleet, no ore for 2+ buckets), out (not in the fleet).
    cells: List[Literal["ore", "quiet", "idle", "out"]]
    cell_m3: List[float]
    volume_m3: float
    # Buckets with ore / buckets in the fleet; null without the scope.
    mining_pct: Optional[int] = None


class FleetMiningEvent(BaseModel):
    at: datetime
    kind: Literal["join", "leave", "ore"]
    character_id: Optional[int] = None
    character_name: Optional[str] = None
    type_id: Optional[int] = None
    ore_name: Optional[str] = None
    quantity: Optional[int] = None
    volume_m3: Optional[float] = None


class FleetMiningTimeline(BaseModel):
    bucket_minutes: int
    start: datetime
    end: datetime
    buckets: List[datetime]
    totals_m3: List[float]
    pilots: List[FleetMiningTimelinePilot]
    # Newest first, at most 200.
    events: List[FleetMiningEvent]


class FleetMiningResponse(BaseModel):
    track_mining: bool
    # True while any pilot's stint still waits for a reading.
    measuring: bool
    updated_at: Optional[datetime] = None
    pilots: List[FleetMiningPilot]
    ores: List[FleetMiningOre]
    volume_m3: float
    isk_estimate: float
    pilots_no_scope: int
    # Null before the fleet starts tracking.
    timeline: Optional[FleetMiningTimeline] = None


ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: FleetMiningResponse, 403: None, 404: None},
    "description": (
        "Ore mined per pilot while they were in the in-game fleet, from "
        "their ESI mining ledger (any system), with m3 and a Jita ISK "
        "estimate, and a timeline: ore per pilot per 15-minute bucket from "
        "the ledger deltas each pull stores, join/leave times, idle runs "
        "(2+ empty buckets in the fleet) and a newest-first log. Live: "
        "readings land about every 15 minutes, and end "
        "readings about 11 minutes after a pilot leaves or the fleet ends "
        "(measuring stays true until then). Pilots without the mining scope "
        "are listed as no_scope. When the fleet hides its roster, only its "
        "FC and Strategic FCs see every name; others see their own pilots "
        "by name and the rest without. Empty for a fleet that never tracked "
        "mining."
    ),
}


def get_fleet_mining(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None

    see_all = sees_all_volunteers(request.user, fleet)
    own_ids = (
        set()
        if see_all
        else {c.character_id for c in user_characters(request.user)}
    )

    def visible(character_id: int) -> bool:
        return see_all or character_id in own_ids

    return FleetMiningResponse(
        **fleet_mining_results(fleet, visible),
        timeline=fleet_mining_timeline(fleet, visible),
    )
