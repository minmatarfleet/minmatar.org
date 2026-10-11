"""PUT /{fleet_id}/my-ship-volunteers — set which ship each of the caller's characters brings."""

from typing import List

from django.db import transaction

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.characters import user_characters

from fleets.endpoints.helpers import (
    _fleet_authorized,
    make_ship_volunteer_response,
)
from fleets.endpoints.schemas import (
    EveFleetShipVolunteerResponse,
    SetMyShipVolunteersRequest,
)
from fleets.helpers.composition import resolve_composition_target
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
        "removes that character. Characters not listed are left unchanged."
    ),
}


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
            resolved.append((selection.character_id, None, None))
            continue
        fitting, fleet_fitting, err = resolve_composition_target(
            fleet, selection.fitting_id, selection.fleet_fitting_id
        )
        if err:
            return 400, {"detail": err}
        resolved.append((selection.character_id, fitting, fleet_fitting))

    with transaction.atomic():
        EveFleetShipVolunteer.objects.filter(
            eve_fleet=fleet,
            character_id__in=[character_id for character_id, _, _ in resolved],
        ).delete()
        EveFleetShipVolunteer.objects.bulk_create(
            [
                EveFleetShipVolunteer(
                    eve_fleet=fleet,
                    character_id=character_id,
                    character_name=allowed[character_id],
                    fitting=fitting,
                    fleet_fitting=fleet_fitting,
                )
                for character_id, fitting, fleet_fitting in resolved
                if fitting or fleet_fitting
            ]
        )

    mine = (
        EveFleetShipVolunteer.objects.filter(
            eve_fleet=fleet, character_id__in=allowed.keys()
        )
        .select_related("fitting", "fleet_fitting")
        .order_by("id")
    )
    return 200, [make_ship_volunteer_response(v) for v in mine]
