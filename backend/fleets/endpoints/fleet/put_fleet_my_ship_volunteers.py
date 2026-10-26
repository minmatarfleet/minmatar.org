"""PUT /{fleet_id}/my-ship-volunteers — set which ship each of the caller's characters brings."""

import logging
from functools import cache
from typing import List

from django.db import transaction

from app.errors import ErrorResponse
from applications.l3arn import is_academy
from authentication import AuthBearer
from eveonline.client import EsiClient, live_esi_allowed
from eveonline.helpers.characters import user_characters
from eveuniverse.models import EveType
from fittings.eft import parse_eft_header

from fleets.endpoints.helpers import (
    _fleet_authorized,
    make_ship_volunteer_response,
    try_refresh_active_fleet_motd,
)
from fleets.endpoints.schemas import (
    EveFleetShipVolunteerResponse,
    SetMyShipVolunteersRequest,
)
from fleets.helpers.composition import (
    academy_keys,
    fleet_composition,
    resolve_composition_target,
)
from fleets.helpers.fit_roles import canonical_bursts, fit_roles
from fleets.helpers.fleet_window import forget_fleet_window
from fleets.helpers.private_fleets import sync_answer_from_ships
from fleets.models import EveFleet, EveFleetShipVolunteer

logger = logging.getLogger(__name__)

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
        "character. ship_type_id instead brings a hull outside the "
        "composition. A selection with none of fitting_id, fleet_fitting_id "
        "or ship_type_id removes that character. Characters not listed are "
        "left unchanged. "
        "bursts picks the command bursts a links fit runs online; omitted, "
        "it defaults to the fit's online bursts. "
        "Academy fits are only for pilots whose main is in the Minmatar "
        "Fleet Academy."
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


SHIP_CATEGORY_ID = 6


def _resolve_hull(type_id: int):
    """(type id, name, error) for an off-doctrine hull: must be a ship."""
    eve_type = (
        EveType.objects.filter(id=type_id).select_related("eve_group").first()
    )
    if eve_type is None and live_esi_allowed():
        try:
            eve_type = EsiClient().get_eve_type(type_id)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Could not look up ship type %s: %s", type_id, e)
            eve_type = None
    if (
        eve_type is None
        or eve_type.eve_group is None
        or eve_type.eve_group.eve_category_id != SHIP_CATEGORY_ID
    ):
        return None, None, "That is not a ship"
    return eve_type.id, eve_type.name, None


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


def _blocked_academy_keys(user, fleet) -> set[str]:
    """Composition keys the user may not bring: Academy fits, unless Academy."""
    if is_academy(user):
        return set()
    return academy_keys(fleet_composition(fleet))


def _resolve_fit(fleet, selection, blocked):
    """(fitting, fleet_fitting, bursts, error) for a composition pick."""
    fitting, fleet_fitting, err = resolve_composition_target(
        fleet, selection.fitting_id, selection.fleet_fitting_id
    )
    if err:
        return None, None, None, err
    key = f"f:{fitting.id}" if fitting else f"m:{fleet_fitting.id}"
    if key in blocked():
        return (
            None,
            None,
            None,
            "Academy ships are for Minmatar Fleet Academy pilots",
        )
    bursts, err = _resolve_bursts(selection, fitting, fleet_fitting)
    return fitting, fleet_fitting, bursts, err


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

    # Fits the caller may not bring; loaded on the first fit picked.
    blocked = cache(lambda: _blocked_academy_keys(request.user, fleet))

    resolved = []
    for selection in payload.selections:
        if selection.character_id not in allowed:
            return 400, {
                "detail": f"Character {selection.character_id} is not one of yours"
            }
        if selection.ship_type_id and (
            selection.fitting_id or selection.fleet_fitting_id
        ):
            return 400, {
                "detail": "Pick a fit or a hull for each character, not both"
            }
        if selection.ship_type_id:
            hull = _resolve_hull(selection.ship_type_id)
            if hull[2]:
                return 400, {"detail": hull[2]}
            resolved.append((selection.character_id, None, None, [], hull[:2]))
            continue
        if selection.fitting_id is None and selection.fleet_fitting_id is None:
            resolved.append((selection.character_id, None, None, [], None))
            continue
        fitting, fleet_fitting, bursts, err = _resolve_fit(
            fleet, selection, blocked
        )
        if err:
            return 400, {"detail": err}
        resolved.append(
            (selection.character_id, fitting, fleet_fitting, bursts, None)
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
        for character_id, fitting, fleet_fitting, bursts, hull in resolved:
            if not (fitting or fleet_fitting or hull):
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
                    ship_type_id=hull[0] if hull else None,
                    ship_name=hull[1] if hull else "",
                    bursts=bursts,
                    solar_system_id=system_id,
                    solar_system_name=system_name,
                )
            )
        EveFleetShipVolunteer.objects.bulk_create(rows)
        # bulk_create sends no signals: picking ships is I'm in on a
        # private fleet (docs/fleets/private-fleets.md).
        sync_answer_from_ships(fleet, request.user.pk)

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
