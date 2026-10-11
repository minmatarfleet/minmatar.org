"""GET /{fleet_id}/supply — contract and market availability per fleet ship."""

from authentication import AuthBearer

from fleets.endpoints.helpers import _fleet_authorized
from fleets.endpoints.schemas import (
    EveFleetSupplyResponse,
    EveFleetSupplyEntryResponse,
)
from fleets.helpers.supply import fleet_supply
from fleets.models import EveFleet

PATH = "/{fleet_id}/supply"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: EveFleetSupplyResponse, 403: None, 404: None},
    "description": (
        "For every ship in the fleet composition: outstanding contracts at "
        "the staging location and how many complete fits the staging market's "
        "sell orders can supply."
    ),
}


def get_fleet_supply(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None
    return EveFleetSupplyResponse(
        entries=[
            EveFleetSupplyEntryResponse(
                key=e.key,
                fitting_id=e.fitting_id,
                fleet_fitting_id=e.fleet_fitting_id,
                contracts=e.contracts,
                market_fits=e.market_fits,
                market_missing=e.market_missing,
            )
            for e in fleet_supply(fleet)
        ],
    )
