from typing import List, Optional

from ninja import Router, Schema

from market.helpers.ops_monitor import build_ops_monitor

router = Router(tags=["Market"])


class OpsUnderstockedContract(Schema):
    location_id: int
    location_name: str
    short_name: str
    fitting_id: int
    fitting_name: str
    ship_id: int
    current_quantity: int
    expected_quantity: int
    shortfall: int
    readiness: str
    expectation_id: int


class OpsSellGapShip(Schema):
    ship_id: int
    fitting_name: str


class OpsSellGap(Schema):
    location_id: int
    location_name: str
    short_name: str
    type_id: int
    item_name: str
    current_quantity: int
    expected_quantity: int
    shortfall: int
    ships: List[OpsSellGapShip] = []


class OpsMonitorSummary(Schema):
    understocked_contracts: int
    sell_gaps: int
    contracts_health_pct: Optional[float] = None
    sell_orders_health_pct: Optional[float] = None
    overall_health_pct: Optional[float] = None
    contract_targets: int = 0
    contract_fulfilled: int = 0
    sell_order_targets: int = 0
    sell_order_fulfilled: int = 0
    contracts_isk: float = 0.0
    sell_orders_isk: float = 0.0
    total_isk_on_market: float = 0.0


class OpsMonitorResponse(Schema):
    synced_at: str
    contracts_synced_at: Optional[str] = None
    orders_synced_at: Optional[str] = None
    understocked_contracts: List[OpsUnderstockedContract]
    sell_gaps: List[OpsSellGap]
    summary: OpsMonitorSummary


@router.get(
    "/ops-monitor",
    description="Staging supply ops monitor queues for alliance market transparency.",
    response=OpsMonitorResponse,
)
def get_ops_monitor(request, location_id: int | None = None):
    return build_ops_monitor(location_id=location_id)
