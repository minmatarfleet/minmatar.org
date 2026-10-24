"""GET /{fleet_id}/participants — what the fleet flew, reships, roles flown, no-shows."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

from authentication import AuthBearer
from eveonline.helpers.characters import user_characters

from fleets.endpoints.helpers import (
    _fleet_authorized,
    _fleet_manager,
    is_strategic_fc,
    make_role_volunteer_response,
    sees_all_volunteers,
)
from fleets.endpoints.schemas import EveFleetRoleVolunteerResponse
from fleets.helpers.participants import (
    EngagementNotFound,
    fleet_no_shows,
    fleet_participants,
)
from fleets.models import EveFleet, EveFleetRoleVolunteer

PATH = "/{fleet_id}/participants"
METHOD = "get"


class FleetParticipantsHullPilot(BaseModel):
    character_id: int
    character_name: str
    # Killmails in the same scope; null without a fight timeline.
    kills: Optional[int] = None
    losses: Optional[int] = None


class FleetParticipantsHull(BaseModel):
    ship_type_id: int
    ship_name: str
    count: int
    # Named pilots only; a hidden roster leaves others out of the list but
    # not out of count.
    pilots: List[FleetParticipantsHullPilot] = []


class FleetParticipantsRolePilot(BaseModel):
    character_id: int
    character_name: str
    ship_name: str


class FleetParticipantsRoleHull(BaseModel):
    ship_name: str
    count: int


class FleetParticipantsRole(BaseModel):
    role: Literal["logi", "links", "cyno"]
    label: str
    pilots: List[FleetParticipantsRolePilot]
    count: int
    hulls: List[FleetParticipantsRoleHull]


class FleetParticipantsNoShow(BaseModel):
    character_id: int
    character_name: str
    ship_name: str
    ship_type_id: int


class FleetParticipantsEngagement(BaseModel):
    position: int  # 1-based index into the fight timeline's rounds
    number: int
    start: datetime
    end: datetime


class FleetParticipantsFight(BaseModel):
    position: int  # 1-based index into the fight timeline's rounds
    kind: Literal["round", "skirmish"]
    number: Optional[int] = None  # rounds only
    start: datetime
    end: datetime
    kills: int
    losses: int


class FleetParticipantsFightDetail(FleetParticipantsFight):
    systems: List[str]
    against: List[str]


class FleetParticipantsInFleet(BaseModel):
    at: datetime
    count: int


class FleetParticipantsEventShip(BaseModel):
    name: str
    count: int


class FleetParticipantsEvent(BaseModel):
    kind: Literal["joined", "reship"]
    at: datetime
    count: int
    ships: List[FleetParticipantsEventShip] = []


class FleetParticipantsShipFlown(BaseModel):
    ship_type_id: int
    ship_name: str
    start: datetime
    end: datetime


class FleetParticipantsCharacter(BaseModel):
    character_id: int
    character_name: str
    joined: datetime
    left: datetime
    kills: Optional[int] = None
    losses: Optional[int] = None
    lost_at: List[datetime] = []
    # The hull flown longest.
    ship_type_id: int
    ship_name: str
    ships: List[FleetParticipantsShipFlown]


class FleetParticipantsPerson(BaseModel):
    # The account's primary character when it flew, else its first in.
    character_id: int
    character_name: str
    registered: bool
    joined: datetime
    kills: Optional[int] = None
    losses: Optional[int] = None
    characters: List[FleetParticipantsCharacter]


class FleetParticipantsPhase(BaseModel):
    start: datetime
    end: datetime
    characters: int
    peak: int
    hulls: List[FleetParticipantsHull]


class FleetParticipantsDoctrineHull(BaseModel):
    ship_type_id: int
    ship_name: str
    count: int


class FleetParticipantsDoctrineSegment(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    positions: List[int]
    doctrine_id: Optional[int] = None
    doctrine_name: Optional[str] = None
    share: int
    pilots: int
    hulls: List[FleetParticipantsDoctrineHull]


class FleetParticipantsResponse(BaseModel):
    pilots: int
    characters: int = 0
    people: int = 0
    on_killmail: Optional[int] = None
    people_on_killmail: Optional[int] = None
    flew: List[FleetParticipantsHull]
    changed_ship: int
    ended_in_pod: int
    roles_flown: List[FleetParticipantsRole]
    logi_fc: List[EveFleetRoleVolunteerResponse]
    engagements: List[FleetParticipantsEngagement] = []
    engagement: Optional[int] = None
    fights: List[FleetParticipantsFight] = []
    fight: Optional[FleetParticipantsFightDetail] = None
    in_fleet: List[FleetParticipantsInFleet] = []
    peak: int = 0
    peak_at: Optional[datetime] = None
    fleet_events: List[FleetParticipantsEvent] = []
    # Whole fleet only (empty for an engagement).
    roster: List[FleetParticipantsPerson] = []
    hidden_pilots: int = 0
    phases: List[FleetParticipantsPhase] = []
    doctrine_flown: List[FleetParticipantsDoctrineSegment] = []
    opsec_filtered: bool = False
    # FC and fleet managers only; null for everyone else.
    no_shows: Optional[List[FleetParticipantsNoShow]] = None
    signed_up: Optional[int] = None
    joined_without_signing_up: Optional[int] = None


ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: FleetParticipantsResponse, 403: None, 404: None},
    "description": (
        "Who flew the fleet, from every tracked instance: hulls by the "
        "non-capsule ship each pilot flew longest, pilots who reshipped or "
        "ended in a pod, and logi, links and cynos from any hull a pilot "
        "flew. pilots and characters count characters; people folds them "
        "into one per account (unregistered characters count alone). "
        "roster lists those people in join order, each with their "
        "characters' ships in order, and is whole-fleet only, as is phases "
        "(the fleet split at reship waves after the form-up, each pilot by "
        "the hull flown longest in that part). in_fleet is the character "
        "count per minute as change points, with peak and peak_at. Kills "
        "and losses come from the fight timeline's matched killmails and "
        "are null without a timeline. A hidden roster names only the "
        "caller's own characters (Strategic FCs see everyone) and "
        "hidden_pilots counts the people left out; counts cover every "
        "pilot. no_shows, "
        "signed_up and joined_without_signing_up are only returned to the "
        "FC and fleet managers, null for everyone else. "
        "engagement=<position> (1-based over the fight timeline's rounds "
        "and skirmishes, the same index the Fights tab uses) counts only "
        "pilots in fleet from a minute before it to a minute after, each by "
        "the hull they were in at the time, with fight describing it; a "
        "missing position or a fleet without a timeline is a 404. "
        "engagements lists the rounds and fights every round and skirmish. "
        "doctrine_flown has one segment per round "
        "(neighbouring rounds on the same doctrine merged; a doctrine needs "
        "half the pilots out of pods in its hulls), one whole-fleet segment "
        "when the timeline has no rounds, and is empty without a timeline. "
        "For viewers who are not Strategic FCs every pilot who flew a "
        "capital, jump freighter, Rorqual, force recon, black ops or cyno "
        "hull is left out of everything and the cyno row is dropped; "
        "opsec_filtered is true for every such viewer."
    ),
}


def get_fleet_participants(
    request, fleet_id: int, engagement: Optional[int] = None
):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None

    own_ids = {c.character_id for c in user_characters(request.user)}
    strategic = is_strategic_fc(request.user)
    see_all = sees_all_volunteers(request.user, fleet)

    def visible(character_id):
        return see_all or character_id in own_ids

    try:
        participants = fleet_participants(
            fleet, visible, engagement=engagement, opsec=not strategic
        )
    except EngagementNotFound:
        return 404, None
    member_ids = participants.pop("member_ids")
    hidden_ids = participants.pop("hidden_ids")
    logi_fc = [
        make_role_volunteer_response(v)
        for v in EveFleetRoleVolunteer.objects.filter(
            eve_fleet=fleet, role=EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR
        ).order_by("id")
        if visible(v.character_id) and v.character_id not in hidden_ids
    ]
    no_shows = {}
    if _fleet_manager(request, fleet):
        no_shows = fleet_no_shows(fleet, member_ids, hidden_ids)
    return FleetParticipantsResponse(
        **participants, logi_fc=logi_fc, **no_shows
    )
