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
    flew: List[FleetParticipantsHull]
    changed_ship: int
    ended_in_pod: int
    roles_flown: List[FleetParticipantsRole]
    logi_fc: List[EveFleetRoleVolunteerResponse]
    engagements: List[FleetParticipantsEngagement] = []
    engagement: Optional[int] = None
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
        "Who flew the fleet, from every tracked instance: hulls by each "
        "pilot's first non-capsule ship, pilots who reshipped or ended in a "
        "pod, and logi, links and cynos from any hull a pilot flew. A hidden "
        "roster names only the caller's own characters in roles flown "
        "(Strategic FCs see everyone); counts cover every pilot. no_shows, "
        "signed_up and joined_without_signing_up are only returned to the "
        "FC and fleet managers, null for everyone else. "
        "engagement=<position> (1-based over the fight timeline's rounds, "
        "the same index the Fights tab uses) counts only pilots in fleet "
        "from a minute before that round to a minute after, each by the "
        "hull they were in at the time; a skirmish, a missing position or a "
        "fleet without a timeline is a 404. engagements lists the rounds "
        "for filter pills. doctrine_flown has one segment per round "
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
    see_all = not fleet.hide_volunteers or strategic

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
