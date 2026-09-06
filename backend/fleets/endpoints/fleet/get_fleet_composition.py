"""GET /{fleet_id}/composition — effective ship list (doctrine + fleet fittings)."""

from typing import List

from authentication import AuthBearer

from fleets.endpoints.helpers import (
    _fleet_authorized,
    make_composition_entry_response,
)
from fleets.endpoints.schemas import EveFleetCompositionEntryResponse
from fleets.helpers.composition import fleet_composition
from fleets.models import EveFleet

PATH = "/{fleet_id}/composition"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: List[EveFleetCompositionEntryResponse],
        403: None,
        404: None,
    },
    "description": (
        "Ships the fleet expects: the doctrine's fittings (if any) followed "
        "by fleet-specific fittings (catalog picks or manual EFT)."
    ),
}


def get_fleet_composition(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    return [
        make_composition_entry_response(e) for e in fleet_composition(fleet)
    ]
