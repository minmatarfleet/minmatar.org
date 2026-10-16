"""POST /{fleet_id}/role-volunteers — sign up a character for a role."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.characters import user_characters

from fleets.endpoints.helpers import (
    _fleet_authorized,
    make_role_volunteer_response,
    try_refresh_active_fleet_motd,
)
from fleets.endpoints.schemas import (
    CreateEveFleetRoleVolunteerRequest,
    EveFleetRoleVolunteerResponse,
)
from fleets.models import EveFleet, EveFleetRoleVolunteer

PATH = "/{fleet_id}/role-volunteers"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetRoleVolunteerResponse,
        403: None,
        404: None,
        400: ErrorResponse,
    },
    "description": (
        "Sign a character up as Logi FC. Character must belong to the user. "
        "Other roles come from ship volunteers."
    ),
}


SIGNUP_ROLES = (EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR,)


def create_fleet_role_volunteer(
    request, fleet_id: int, payload: CreateEveFleetRoleVolunteerRequest
):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    allowed_ids = {
        c.character_id: c.character_name for c in user_characters(request.user)
    }
    if payload.character_id not in allowed_ids:
        return 400, {
            "detail": "Character not found or not one of your characters"
        }
    # Links, cynos and logi come from the ships pilots volunteer for. Logi
    # FC is a person, not a ship, so it is the one role still signed up for.
    if payload.role not in SIGNUP_ROLES:
        return 400, {
            "detail": (
                "Only Logi FC is signed up for. Links and cynos come from "
                "the ship you volunteer."
            )
        }
    volunteer, _ = EveFleetRoleVolunteer.objects.update_or_create(
        eve_fleet=fleet,
        character_id=payload.character_id,
        role=payload.role,
        defaults={
            "character_name": allowed_ids[payload.character_id],
            "subtype": None,
            "quantity": None,
        },
    )
    try_refresh_active_fleet_motd(fleet)
    return 200, make_role_volunteer_response(volunteer, reveal_system=True)
