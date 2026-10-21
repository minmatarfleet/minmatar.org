"""GET /{fleet_id}/fights/report — the battle report for the fleet or a window."""

from datetime import datetime
from typing import List, Optional

from django.utils import timezone
from pydantic import BaseModel

from authentication import AuthBearer
from groups.helpers.feature_access import can_use_feature
from intel.affiliations.resolve import (
    bloc_for_group,
    bloc_map,
    public_entry,
)

from fleets.endpoints.helpers import _fleet_authorized, _fleet_manager
from fleets.endpoints.schemas import FleetBattleSegment
from fleets.helpers.fights.battle import build_window_report, ensure_snapshot
from fleets.helpers.fights.serve import may_view
from fleets.helpers.fights.timeline import is_live
from fleets.models import (
    EveFleet,
    EveFleetBattleSegment,
    EveFleetFightTimeline,
    EveFleetInstance,
)

PATH = "/{fleet_id}/fights/report"
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


class FleetBattleBloc(BaseModel):
    id: int
    name: str
    # Still only suggested in the intel affiliation database.
    likely: bool


class FleetBattleGroup(BaseModel):
    id: int
    kind: str
    name: str
    pilots: int
    ships_lost: int
    isk_lost: int
    # The bloc the group really flies for, for viewers with intel access.
    bloc: Optional[FleetBattleBloc] = None


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


class FleetBattleActivity(BaseModel):
    minute: datetime
    # ISK lost that minute by team 0, 1 and 2, on the whole fleet's sides.
    isk: List[int]


class FleetBattleWindow(BaseModel):
    start: datetime
    end: datetime


class FleetBattleReportResponse(BaseModel):
    """Every killmail around the fleet, or in a window of it, split into
    sides."""

    fleet_id: int
    # True when no window was asked for: the whole fleet.
    whole: bool
    window_start: datetime
    window_end: datetime
    # The first and last mail in the window.
    start: datetime
    end: datetime
    minutes: int
    # The whole fleet, from its first mail minus a minute to its last plus
    # a minute.
    span_start: datetime
    span_end: datetime
    systems: List[FleetBattleSystem]
    complete: bool
    sides: str
    teams: List[FleetBattleTeam]
    killmails: List[FleetBattleKillmail]
    activity: List[FleetBattleActivity]
    # The fleet's rounds, padded a minute each side, for picking one.
    fights: List[FleetBattleWindow]
    segments: List[FleetBattleSegment]
    segment_id: Optional[int] = None
    can_edit_segments: bool


ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: FleetBattleReportResponse, 403: None, 404: None},
    "description": (
        "A battle report for the whole fleet: every killmail around its "
        "fights, third parties included, with up to three sides. ``start`` "
        "and ``end`` scope it to a window, and ``segment`` to a window the "
        "FC saved. Sides are worked out from the window's own mails. Team "
        "0 is ours. Groups are alliances, or corporations outside one. "
        "``sides`` moves groups between teams, e.g. 99000001:1,98000002:0; "
        "the response echoes the moves it applied. isk_destroyed is the ISK "
        "other teams lost on mails the team was on. activity is ISK lost "
        "per minute over the whole fleet, by team. complete is false when "
        "the killmail feed had already purged the mails and the report only "
        "has the mails our fleet was on. Same access rules as GET /fights."
    ),
}


def get_fleet_fight_report(
    request,
    fleet_id: int,
    start: datetime = None,
    end: datetime = None,
    segment: int = None,
    sides: str = None,
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
    segments = list(EveFleetBattleSegment.objects.filter(eve_fleet=fleet))
    if segment is not None:
        chosen = next((s for s in segments if s.id == segment), None)
        if chosen is None:
            return 404, None
        start, end = chosen.start, chosen.end
    ensure_snapshot(timeline, now=timezone.now())
    report = build_window_report(timeline, start, end, sides)
    if report is None:
        return 404, None
    if can_use_feature(request.user, "intel.view"):
        _add_blocs(report)
    report["segments"] = [
        {"id": s.id, "name": s.name, "start": s.start, "end": s.end}
        for s in segments
    ]
    report["segment_id"] = segment
    report["can_edit_segments"] = request.user == fleet.created_by
    return report


def _add_blocs(report: dict) -> None:
    blocs = bloc_map()
    for team in report.get("teams") or []:
        for group in team.get("groups") or []:
            group["bloc"] = public_entry(
                bloc_for_group(group["kind"], group["id"], blocs=blocs)
            )
