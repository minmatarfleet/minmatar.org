"""PUT /{fleet_id}/my-ship-volunteers — set which ship each of the caller's characters brings."""

from typing import List

from django.db import transaction

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.characters import user_characters
from eveuniverse.models import EveType

from fleets.endpoints.helpers import (
    _fleet_authorized,
    make_ship_volunteer_response,
    try_refresh_active_fleet_motd,
)
from fleets.endpoints.schemas import (
    EveFleetShipVolunteerResponse,
    SetMyShipVolunteersRequest,
)
from fleets.helpers.composition import resolve_composition_target
from fleets.helpers.eft_items import parse_eft_header
from fleets.helpers.fit_roles import canonical_bursts, fit_roles
from fleets.helpers.fleet_window import forget_fleet_window
from fleets.models import EveFleet, EveFleetShipVolunteer

PATH = "/{fleet_id}/my-ship-volunteers"
METHOD = "put"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: List[EveFleetShipVolunteerResponse],
        400: ErrorResponse,
        403: None,
        404: None,
    },
    "description": (
        "Replace the caller's ship volunteers for this fleet: one ship per "
        "character. A selection with neither fitting_id nor fleet_fitting_id "
        "removes that character. Characters not listed are left unchanged. "
        "bursts picks the command bursts a links fit runs online; omitted, "
        "it defaults to the fit's online bursts."
    ),
}


def _ship_group(eft: str) -> str:
    ship_name, _ = parse_eft_header(eft)
    row = (
        EveType.objects.filter(name__iexact=ship_name)
        .values_list("eve_group__name", flat=True)
        .first()
    )
    return row or ""


def _resolve_bursts(selection, fitting, fleet_fitting):
    """(bursts, error) for a selection on its resolved target."""
    eft = fitting.eft_format if fitting else fleet_fitting.effective_eft
    roles = fit_roles(eft, _ship_group(eft))
    if selection.bursts is None:
        return roles.default_bursts(), None
    error = roles.validate_bursts(selection.bursts)
    if error:
        return None, error
    return canonical_bursts(selection.bursts), None


def set_my_ship_volunteers(
    request, fleet_id: int, payload: SetMyShipVolunteersRequest
):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    allowed = {
        c.character_id: c.character_name for c in user_characters(request.user)
    }

    resolved = []
    for selection in payload.selections:
        if selection.character_id not in allowed:
            return 400, {
                "detail": f"Character {selection.character_id} is not one of yours"
            }
        if selection.fitting_id is None and selection.fleet_fitting_id is None:
            resolved.append((selection.character_id, None, None, []))
            continue
        fitting, fleet_fitting, err = resolve_composition_target(
            fleet, selection.fitting_id, selection.fleet_fitting_id
        )
        if err:
            return 400, {"detail": err}
        bursts, err = _resolve_bursts(selection, fitting, fleet_fitting)
        if err:
            return 400, {"detail": err}
        resolved.append(
            (selection.character_id, fitting, fleet_fitting, bursts)
        )

    character_ids = [row[0] for row in resolved]
    with transaction.atomic():
        existing = EveFleetShipVolunteer.objects.filter(
            eve_fleet=fleet, character_id__in=character_ids
        )
        # Re-saving the same ship keeps the FC's cyno system assignment.
        systems = {
            (v.character_id, v.fitting_id, v.fleet_fitting_id): (
                v.solar_system_id,
                v.solar_system_name,
            )
            for v in existing
            if v.solar_system_name
        }
        existing.delete()
        rows = []
        for character_id, fitting, fleet_fitting, bursts in resolved:
            if not (fitting or fleet_fitting):
                continue
            system_id, system_name = systems.get(
                (
                    character_id,
                    fitting.id if fitting else None,
                    fleet_fitting.id if fleet_fitting else None,
                ),
                (None, ""),
            )
            rows.append(
                EveFleetShipVolunteer(
                    eve_fleet=fleet,
                    character_id=character_id,
                    character_name=allowed[character_id],
                    fitting=fitting,
                    fleet_fitting=fleet_fitting,
                    bursts=bursts,
                    solar_system_id=system_id,
                    solar_system_name=system_name,
                )
            )
        EveFleetShipVolunteer.objects.bulk_create(rows)

    forget_fleet_window(fleet.id)
    # Cynos in the MOTD come from ship volunteers.
    try_refresh_active_fleet_motd(fleet)

    mine = (
        EveFleetShipVolunteer.objects.filter(
            eve_fleet=fleet, character_id__in=allowed.keys()
        )
        .select_related("fitting", "fleet_fitting")
        .order_by("id")
    )
    return 200, [
        make_ship_volunteer_response(v, reveal_system=True) for v in mine
    ]
