from ninja import Router

from market.endpoints.health_schemas import MarketHealthResponse
from market.helpers.health_snapshot import (
    HISTORY_DAYS_DEFAULT,
    get_market_health,
)

router = Router(tags=["Market"])


@router.get(
    "/health",
    description="Combined contract and sell-order health snapshots for a market-active location.",
    response=MarketHealthResponse,
)
def get_market_health_endpoint(
    request,
    location_id: int,
    days: int = HISTORY_DAYS_DEFAULT,
):
    return get_market_health(location_id=location_id, days=days)
