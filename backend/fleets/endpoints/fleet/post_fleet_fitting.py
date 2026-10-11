"""POST /{fleet_id}/fittings — FC adds a catalog or manual fit to the fleet."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from fittings.models import EveFitting

from fleets.endpoints.helpers import (
    _fleet_authorized,
    _fleet_manager,
    make_composition_entry_response,
    try_refresh_active_fleet_motd,
)
from fleets.endpoints.schemas import (
    CreateEveFleetFittingRequest,
    EveFleetCompositionEntryResponse,
)
from fleets.helpers.composition import fleet_composition, ship_id_for_eft
from fleets.helpers.esi_fittings import (
    fitting_publisher,
    missing_scope_detail,
    publish_and_store,
)
from fleets.models import EveFleet, EveFleetFitting

PATH = "/{fleet_id}/fittings"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetCompositionEntryResponse,
        400: ErrorResponse,
        403: None,
        404: None,
    },
    "description": (
        "Add a ship to the fleet composition. Pass fitting_id for a catalog "
        "fitting (makeshift doctrine) or eft_format for a manual fit. Fleet "
        "commander only. Manual fits are saved in-game under the FC (needs "
        "esi-fittings.write_fittings.v1) so the MOTD can link them."
    ),
}

VALID_ROLES = {c[0] for c in EveFleetFitting.ROLE_CHOICES}


def create_fleet_fitting(
    request, fleet_id: int, payload: CreateEveFleetFittingRequest
):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    if not _fleet_manager(request, fleet):
        return 403, None
    if payload.role not in VALID_ROLES:
        return 400, {
            "detail": f"Invalid role. Must be one of: {sorted(VALID_ROLES)}"
        }

    eft = (payload.eft_format or "").strip()
    if bool(payload.fitting_id) == bool(eft):
        return 400, {
            "detail": "Provide exactly one of fitting_id or eft_format"
        }

    next_order = EveFleetFitting.objects.filter(eve_fleet=fleet).count()

    if payload.fitting_id:
        fitting = EveFitting.objects.filter(id=payload.fitting_id).first()
        if not fitting:
            return 400, {"detail": "Fitting not found"}
        if EveFleetFitting.objects.filter(
            eve_fleet=fleet, fitting=fitting
        ).exists():
            return 400, {"detail": "That fitting is already in the fleet"}
        fleet_fitting = EveFleetFitting.objects.create(
            eve_fleet=fleet,
            fitting=fitting,
            name=fitting.name,
            ship_id=fitting.ship_id,
            role=payload.role,
            order=next_order,
        )
    else:
        ship_id = ship_id_for_eft(eft)
        if not ship_id:
            return 400, {
                "detail": (
                    "Could not recognise the ship in the EFT header "
                    "([Ship, Fit name])"
                )
            }
        publisher = fitting_publisher(request.user)
        if not publisher:
            return 400, {"detail": missing_scope_detail()}
        name = EveFitting.fitting_name_from_eft(
            eft
        ) or EveFitting.ship_name_from_eft(eft)
        fleet_fitting = EveFleetFitting.objects.create(
            eve_fleet=fleet,
            fitting=None,
            name=name,
            ship_id=ship_id,
            eft_format=eft,
            role=payload.role,
            order=next_order,
        )
        publish_and_store(
            fleet_fitting, publisher, fleet.id, name, "fit", name, eft
        )

    try_refresh_active_fleet_motd(fleet)
    entry = next(
        e
        for e in fleet_composition(fleet)
        if e.fleet_fitting_id == fleet_fitting.id
        or (
            fleet_fitting.fitting_id
            and e.fitting_id == fleet_fitting.fitting_id
        )
    )
    return 200, make_composition_entry_response(entry)
