"""GET /{fleet_id}/participants — what the fleet flew, reships, roles flown, no-shows."""

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
from fleets.helpers.participants import fleet_no_shows, fleet_participants
from fleets.models import EveFleet, EveFleetRoleVolunteer

PATH = "/{fleet_id}/participants"
METHOD = "get"


class FleetParticipantsHull(BaseModel):
    ship_type_id: int
    ship_name: str
    count: int


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


class FleetParticipantsResponse(BaseModel):
    pilots: int
    flew: List[FleetParticipantsHull]
    changed_ship: int
    ended_in_pod: int
    roles_flown: List[FleetParticipantsRole]
    logi_fc: List[EveFleetRoleVolunteerResponse]
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
        "FC and fleet managers, null for everyone else."
    ),
}


def get_fleet_participants(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None

    own_ids = {c.character_id for c in user_characters(request.user)}
    see_all = not fleet.hide_volunteers or is_strategic_fc(request.user)

    def visible(character_id):
        return see_all or character_id in own_ids

    participants = fleet_participants(fleet, visible)
    member_ids = participants.pop("member_ids")
    logi_fc = [
        make_role_volunteer_response(v)
        for v in EveFleetRoleVolunteer.objects.filter(
            eve_fleet=fleet, role=EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR
        ).order_by("id")
        if visible(v.character_id)
    ]
    no_shows = {}
    if _fleet_manager(request, fleet):
        no_shows = fleet_no_shows(fleet, member_ids)
    return FleetParticipantsResponse(
        **participants, logi_fc=logi_fc, **no_shows
    )
