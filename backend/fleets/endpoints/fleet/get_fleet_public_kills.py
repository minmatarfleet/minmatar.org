"""GET /{fleet_id}/public-kills — a finished fleet's kills, for anyone."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

from authentication import AuthOptional
from feed.helpers.fleet_kills import fleet_kill_report

from fleets.helpers.fights.serve import pilot_numbers
from fleets.helpers.fleet_boss import in_game_fleet_commander
from fleets.helpers.visibility import public_kills_allowed
from fleets.models import EveFleet, EveFleetFightTimeline, EveFleetInstance

PATH = "/{fleet_id}/public-kills"
METHOD = "get"


class FleetPublicKillmail(BaseModel):
    killmail_id: int
    killmail_time: datetime
    outcome: Literal["kill", "loss"]
    victim_ship_type_id: Optional[int] = None
    victim_ship_name: str
    victim_character_id: Optional[int] = None
    victim_name: Optional[str] = None
    # Not stored with the fleet's kill rows yet.
    victim_corporation_id: Optional[int] = None
    victim_alliance_id: Optional[int] = None
    solar_system_name: str
    isk_value: int
    is_capsule: bool


class FleetPublicKillsResponse(BaseModel):
    fleet_id: int
    title: str
    fleet_type: str
    fc_character_id: Optional[int] = None
    fc_name: Optional[str] = None
    start: datetime
    end: datetime
    systems: List[str]
    ships_destroyed: int
    ships_lost: int
    isk_destroyed: int
    isk_lost: int
    efficiency: Optional[int] = None
    # How many flew against how many they fought; never who.
    our_pilots: Optional[int] = None
    hostile_pilots: Optional[int] = None
    killmails: List[FleetPublicKillmail]


ROUTE_SPEC = {
    "auth": AuthOptional(),
    "response": {200: FleetPublicKillsResponse, 404: None},
    "description": (
        "What a finished fleet killed and lost, for a public page; no login "
        "needed. 404 until every tracked instance has ended, and always for "
        "cancelled fleets, members-only tribe group fleets and fleets for a "
        "hidden audience. Only what the killmails already show publicly: "
        "the roster, doctrine, staging and description are never included. "
        "Killmails are newest first; totals count capsules towards ISK but "
        "not ships. our_pilots counts the pilots tracked in the fleet and "
        "hostile_pilots the hostiles on its killmails; both are null until "
        "there is something to count."
    ),
}


def _killmail(row: dict) -> dict:
    # Victims are on the public killmail, ours included.
    return {
        "killmail_id": row["killmail_id"],
        "killmail_time": row["killmail_time"],
        "outcome": row["outcome"],
        "victim_ship_type_id": row.get("victim_ship_type_id"),
        "victim_ship_name": row.get("victim_ship_name") or "",
        "victim_character_id": row.get("victim_character_id"),
        "victim_name": row.get("victim_character_name") or None,
        "victim_corporation_id": None,
        "victim_alliance_id": None,
        "solar_system_name": row.get("solar_system_name") or "",
        "isk_value": row["isk_value"],
        "is_capsule": row["is_capsule"],
    }


def get_fleet_public_kills(request, fleet_id: int):
    fleet = (
        EveFleet.objects.filter(id=fleet_id).select_related("audience").first()
    )
    if not fleet or not public_kills_allowed(fleet):
        return 404, None
    spans = list(
        EveFleetInstance.objects.filter(eve_fleet=fleet).values_list(
            "start_time", "end_time"
        )
    )
    if not spans or any(end is None for _, end in spans):
        return 404, None

    report = fleet_kill_report(fleet)
    killmails = [_killmail(row) for row in report["killmails"]]
    systems = []
    for row in reversed(killmails):
        if row["solar_system_name"] not in systems:
            systems.append(row["solar_system_name"])
    destroyed, lost = report["isk_destroyed"], report["isk_lost"]
    timeline = EveFleetFightTimeline.objects.filter(eve_fleet=fleet).first()
    numbers = pilot_numbers(fleet, timeline.killmails if timeline else None)
    # Public: the character that ran the fleet in game, never the main
    # behind an alt (docs/fleets/fleet-on-alt.md).
    fc = in_game_fleet_commander(fleet)
    return FleetPublicKillsResponse(
        fleet_id=fleet.id,
        title=fleet.objective or f"Fleet {fleet.id}",
        fleet_type=fleet.type,
        fc_character_id=fc.character_id if fc else None,
        fc_name=fc.character_name if fc else None,
        start=min(start for start, _ in spans),
        end=max(end for _, end in spans),
        systems=systems,
        ships_destroyed=report["ships_destroyed"],
        ships_lost=report["ships_lost"],
        isk_destroyed=destroyed,
        isk_lost=lost,
        efficiency=(
            round(100 * destroyed / (destroyed + lost))
            if destroyed + lost
            else None
        ),
        **numbers,
        killmails=killmails,
    )
