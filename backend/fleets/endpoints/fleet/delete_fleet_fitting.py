"""DELETE /{fleet_id}/fittings/{fleet_fitting_id} — FC removes a fleet fitting."""

from authentication import AuthBearer

from fleets.endpoints.helpers import (
    _fleet_authorized,
    _fleet_manager,
    try_refresh_active_fleet_motd,
)
from fleets.helpers.esi_fittings import unpublish
from fleets.models import EveFleet, EveFleetFitting

PATH = "/{fleet_id}/fittings/{fleet_fitting_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {204: None, 403: None, 404: None},
    "description": (
        "Remove a fleet fitting. Ship volunteers and refits attached to a "
        "manual fit are removed with it. Fleet commander only."
    ),
}


def delete_fleet_fitting(request, fleet_id: int, fleet_fitting_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    if not _fleet_manager(request, fleet):
        return 403, None
    fleet_fitting = EveFleetFitting.objects.filter(
        id=fleet_fitting_id, eve_fleet=fleet
    ).first()
    if not fleet_fitting:
        return 404, None
    unpublish(fleet_fitting)
    fleet_fitting.delete()
    try_refresh_active_fleet_motd(fleet)
    return 204, None
