"""DELETE /{fleet_id}/refits/{refit_id} — FC removes a fleet refit."""

from authentication import AuthBearer

from fleets.endpoints.helpers import (
    _fleet_authorized,
    _fleet_manager,
    try_refresh_active_fleet_motd,
)
from fleets.helpers.esi_fittings import unpublish
from fleets.models import EveFleet, EveFleetFittingRefit

PATH = "/{fleet_id}/refits/{refit_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {204: None, 403: None, 404: None},
    "description": "Remove a fleet refit. Fleet commander only.",
}


def delete_fleet_refit(request, fleet_id: int, refit_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    if not _fleet_manager(request, fleet):
        return 403, None
    fleet_refit = EveFleetFittingRefit.objects.filter(
        id=refit_id, eve_fleet=fleet
    ).first()
    if not fleet_refit:
        return 404, None
    unpublish(fleet_refit)
    fleet_refit.delete()
    try_refresh_active_fleet_motd(fleet)
    return 204, None
