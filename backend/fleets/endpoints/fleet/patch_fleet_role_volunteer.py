"""PATCH /{fleet_id}/role-volunteers/{volunteer_id} — FC assigns a cyno system."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveuniverse.models import EveSolarSystem

from fleets.endpoints.helpers import (
    _fleet_authorized,
    _fleet_manager,
    make_role_volunteer_response,
)
from fleets.helpers.cyno_notifications import notify_cyno_system_assignment
from fleets.endpoints.schemas import (
    AssignRoleVolunteerSystemRequest,
    EveFleetRoleVolunteerResponse,
)
from fleets.models import EveFleet, EveFleetRoleVolunteer

PATH = "/{fleet_id}/role-volunteers/{volunteer_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetRoleVolunteerResponse,
        400: ErrorResponse,
        403: None,
        404: None,
    },
    "description": (
        "Assign (or clear) the solar system for a cyno volunteer. Fleet "
        "commander only. Send both fields null to clear. The system is "
        "private: it is DM'd to the pilot on Discord and never shown in "
        "the MOTD."
    ),
}


def assign_fleet_role_volunteer_system(
    request,
    fleet_id: int,
    volunteer_id: int,
    payload: AssignRoleVolunteerSystemRequest,
):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    if not _fleet_manager(request, fleet):
        return 403, None
    volunteer = EveFleetRoleVolunteer.objects.filter(
        id=volunteer_id, eve_fleet=fleet
    ).first()
    if not volunteer:
        return 404, None
    if volunteer.role != EveFleetRoleVolunteer.ROLE_CYNO:
        return 400, {"detail": "Only cyno volunteers can be assigned a system"}

    system_name = (payload.solar_system_name or "").strip()
    system_id = payload.solar_system_id
    if system_id and not system_name:
        # Best effort: resolve the name from the universe cache.
        system = EveSolarSystem.objects.filter(id=system_id).first()
        if not system:
            return 400, {
                "detail": "solar_system_name is required for unknown system ids"
            }
        system_name = system.name

    had_system = bool(volunteer.solar_system_name)
    volunteer.solar_system_id = system_id if system_name else None
    volunteer.solar_system_name = system_name
    volunteer.save(update_fields=["solar_system_id", "solar_system_name"])
    if system_name:
        notify_cyno_system_assignment(fleet, volunteer)
    elif had_system:
        notify_cyno_system_assignment(fleet, volunteer, cleared=True)
    return 200, make_role_volunteer_response(volunteer, reveal_system=True)
