from ninja import Router
from ninja.errors import HttpError

from market.endpoints.health_schemas import LiveSellOrderSupplyResponse
from market.helpers.sell_order_health import get_live_sell_order_supply

router = Router(tags=["Market"])


@router.get(
    "/sell-order-supply",
    description="Live sell-order supply browse for a market-active location.",
    response=LiveSellOrderSupplyResponse,
)
def get_sell_order_supply_endpoint(request, location_id: int):
    payload = get_live_sell_order_supply(location_id=location_id)
    if payload is None:
        raise HttpError(404, "Location not found or not market-active")
    return payload
