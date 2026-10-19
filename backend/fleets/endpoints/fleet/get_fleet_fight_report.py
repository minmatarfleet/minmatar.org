"""GET /{fleet_id}/fights/{position}/report — one round's battle report."""

from datetime import datetime
from typing import List, Optional

from django.utils import timezone
from pydantic import BaseModel

from authentication import AuthBearer

from fleets.endpoints.helpers import _fleet_authorized, _fleet_manager
from fleets.helpers.fights.battle import build_report, ensure_snapshot
from fleets.helpers.fights.serve import may_view
from fleets.helpers.fights.timeline import is_live
from fleets.models import EveFleet, EveFleetFightTimeline, EveFleetInstance

PATH = "/{fleet_id}/fights/{position}/report"
METHOD = "get"


class FleetBattleSystem(BaseModel):
    id: int
    name: str


class FleetBattleTotals(BaseModel):
    pilots: int
    # Damage the team's pilots dealt on these mails.
    damage: int = 0
    ships_lost: int
    pods_lost: int
    isk_lost: int
    isk_destroyed: int
    efficiency: Optional[int] = None


class FleetBattleGroup(BaseModel):
    id: int
    kind: str
    name: str
    pilots: int
    ships_lost: int
    isk_lost: int


class FleetBattleShip(BaseModel):
    type_id: Optional[int] = None
    name: str
    lost: bool
    killmail_id: Optional[int] = None


class FleetBattlePilot(BaseModel):
    character_id: int
    name: str
    corporation_id: Optional[int] = None
    corporation_name: str = ""
    alliance_id: Optional[int] = None
    alliance_name: str = ""
    group_id: Optional[int] = None
    ships: List[FleetBattleShip]
    kills: int
    damage: int


class FleetBattleTeam(BaseModel):
    index: int
    ours: bool
    totals: FleetBattleTotals
    groups: List[FleetBattleGroup]
    pilots: List[FleetBattlePilot]


class FleetBattleFinalBlow(BaseModel):
    character_id: int
    name: str
    ship_type_id: Optional[int] = None


class FleetBattleKillmail(BaseModel):
    id: int
    time: datetime
    system_id: int
    system_name: str
    ship_type_id: Optional[int] = None
    ship_name: str
    victim_id: Optional[int] = None
    victim_name: str
    victim_corporation_id: Optional[int] = None
    victim_alliance_id: Optional[int] = None
    victim_group_id: Optional[int] = None
    team: int
    isk: int
    pod: bool
    attackers: int
    final_blow: Optional[FleetBattleFinalBlow] = None


class FleetBattleReportResponse(BaseModel):
    """Every killmail in a round's systems from its first mail minus a
    minute to its last plus a minute, split into sides."""

    fleet_id: int
    position: int
    kind: str
    number: Optional[int] = None
    start: datetime
    end: datetime
    minutes: int
    window_start: datetime
    window_end: datetime
    systems: List[FleetBattleSystem]
    complete: bool
    sides: str
    teams: List[FleetBattleTeam]
    killmails: List[FleetBattleKillmail]


ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: FleetBattleReportResponse, 403: None, 404: None},
    "description": (
        "A battle report for round or skirmish ``position`` (1-based, in "
        "the order of GET /fights rounds): every killmail in its systems "
        "from its first mail minus a minute to its last plus a minute, "
        "third parties included, with up to three sides. Team 0 is ours. "
        "Groups are alliances, or corporations outside one. ``sides`` "
        "moves groups between teams, e.g. 99000001:1,98000002:0; the "
        "response echoes the moves it applied. isk_destroyed is the ISK "
        "other teams lost on mails the team was on. complete is false when "
        "the killmail feed had already purged the mails and the report only "
        "has the mails our fleet was on. Same access rules as GET /fights."
    ),
}


def get_fleet_fight_report(
    request, fleet_id: int, position: int, sides: str = None
):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if (
        not fleet
        or not EveFleetInstance.objects.filter(eve_fleet=fleet).exists()
    ):
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    manager = _fleet_manager(request, fleet)
    if not may_view(request.user, fleet, manager=manager, live=is_live(fleet)):
        return 403, None
    timeline = EveFleetFightTimeline.objects.filter(eve_fleet=fleet).first()
    if timeline is None or not timeline.payload:
        return 404, None
    ensure_snapshot(timeline, now=timezone.now())
    report = build_report(timeline, position, sides)
    if report is None:
        return 404, None
    return report
