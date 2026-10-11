"""POST /{fleet_id}/refits — FC adds a refit (curated or custom) for a doctrine fit."""

from django.db import IntegrityError, transaction

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.endpoints.helpers import (
    _fleet_authorized,
    _fleet_manager,
    make_fleet_refit_response,
    try_refresh_active_fleet_motd,
)
from fleets.endpoints.schemas import (
    CreateEveFleetFittingRefitRequest,
    EveFleetFittingRefitResponse,
)
from fleets.helpers.composition import resolve_composition_target
from fleets.helpers.eft_items import refit_eft_from_swaps
from fleets.helpers.esi_fittings import (
    fitting_publisher,
    missing_scope_detail,
    publish_and_store,
)
from fleets.helpers.refits import (
    default_refit_label,
    format_cargo_modules,
    parse_cargo_modules,
    refit_cargo_diff,
    resolve_fitting_refit,
)
from fleets.models import EveFleet, EveFleetFittingRefit

PATH = "/{fleet_id}/refits"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetFittingRefitResponse,
        400: ErrorResponse,
        403: None,
        404: None,
    },
    "description": (
        "Add a refit for one of the fleet composition's fittings "
        "(fitting_id or fleet_fitting_id). Fleet "
        "commander only. Pass refit_id to use a curated refit (cargo is "
        "derived from the EFT diff unless cargo_modules is given), swaps "
        "for a custom slot-swap refit, or name + cargo_modules for a plain "
        "cargo list. Refits with a full EFT are saved in-game under the "
        "FC (needs esi-fittings.write_fittings.v1) and linked in the MOTD."
    ),
}


def _swap_pairs(payload) -> list[tuple[str, str]]:
    pairs = [
        (s.module_out.strip(), s.module_in.strip())
        for s in payload.swaps or []
    ]
    return [(out, in_) for out, in_ in pairs if out and in_]


def _refit_name(payload, fitting, refit, swaps) -> str:
    name = (payload.name or "").strip()
    if not name and refit:
        name = default_refit_label(fitting, refit)
    if not name and swaps:
        swapped_in = list(dict.fromkeys(in_ for _, in_ in swaps))
        name = (
            f"{swapped_in[0]} +{len(swapped_in) - 1}"
            if len(swapped_in) > 1
            else swapped_in[0]
        )
    return name


def _refit_eft(fitting, fleet_fitting, refit, swaps, name):
    """Full EFT of the refitted ship, or "" for a plain cargo list."""
    if refit:
        return refit.eft_format, None
    if swaps:
        base = fitting.eft_format if fitting else fleet_fitting.effective_eft
        return refit_eft_from_swaps(base, swaps, name)
    return "", None


def _refit_cargo(payload, fitting, refit, swaps) -> str:
    if payload.cargo_modules is not None:
        return format_cargo_modules(parse_cargo_modules(payload.cargo_modules))
    if refit:
        return format_cargo_modules(
            refit_cargo_diff(fitting.eft_format, refit.eft_format)
        )
    if swaps:
        return format_cargo_modules(
            parse_cargo_modules("\n".join(in_ for _, in_ in swaps))
        )
    return ""


def _refit_notes(payload, swaps) -> str:
    notes = (payload.notes or "").strip()
    if not notes and swaps:
        notes = "; ".join(f"{out} → {in_}" for out, in_ in swaps)[:200]
    return notes


def _resolve_targets(fleet, payload):
    """(fitting, fleet_fitting, curated refit, error_detail)."""
    fitting, fleet_fitting, err = resolve_composition_target(
        fleet, payload.fitting_id, payload.fleet_fitting_id
    )
    if err:
        return None, None, None, err
    refit = None
    if payload.refit_id is not None:
        if not fitting:
            return None, None, None, "Manual fits have no curated refits"
        refit, err = resolve_fitting_refit(fitting, payload.refit_id)
        if err:
            return None, None, None, err
    return fitting, fleet_fitting, refit, None


def _build_refit(request, fleet, payload):
    """Validate the payload and create the row. Returns (refit, error)."""
    fitting, fleet_fitting, refit, err = _resolve_targets(fleet, payload)
    if err:
        return None, err

    swaps = _swap_pairs(payload)
    name = _refit_name(payload, fitting, refit, swaps)
    if not name:
        return None, "A refit name is required for custom refits"

    eft, err = _refit_eft(fitting, fleet_fitting, refit, swaps, name)
    if err:
        return None, err

    # Anything with a full EFT is saved in-game under the FC.
    publisher = fitting_publisher(request.user) if eft else None
    if eft and not publisher:
        return None, missing_scope_detail()

    try:
        with transaction.atomic():
            fleet_refit = EveFleetFittingRefit.objects.create(
                eve_fleet=fleet,
                fitting=fitting,
                fleet_fitting=fleet_fitting,
                refit=refit,
                name=name,
                cargo_modules=_refit_cargo(payload, fitting, refit, swaps),
                notes=_refit_notes(payload, swaps),
                eft_format=eft,
            )
    except IntegrityError:
        return None, "A refit with this name already exists for that fitting"

    if publisher:
        label = f"{fleet_refit.target_name} → {name}"
        publish_and_store(
            fleet_refit, publisher, fleet.id, label, "refit", label, eft
        )
    return fleet_refit, None


def create_fleet_refit(
    request, fleet_id: int, payload: CreateEveFleetFittingRefitRequest
):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    if not _fleet_manager(request, fleet):
        return 403, None

    fleet_refit, err = _build_refit(request, fleet, payload)
    if err:
        return 400, {"detail": err}
    try_refresh_active_fleet_motd(fleet)
    return 200, make_fleet_refit_response(fleet_refit)
