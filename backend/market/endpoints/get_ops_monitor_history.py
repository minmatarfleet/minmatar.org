from typing import List, Optional

from ninja import Router, Schema

from market.helpers.ops_snapshot import list_ops_monitor_snapshots

router = Router(tags=["Market"])


class OpsMonitorHistoryProblemContract(Schema):
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


class OpsMonitorHistorySellGapShip(Schema):
    ship_id: int
    fitting_name: str


class OpsMonitorHistorySellGap(Schema):
    location_id: int
    location_name: str
    short_name: str
    type_id: int
    item_name: str
    current_quantity: int
    viable_quantity: int
    expected_quantity: int
    shortfall: int
    ships: List[OpsMonitorHistorySellGapShip] = []


class OpsMonitorHistoryPoint(Schema):
    id: int
    captured_at: str
    location_id: int
    location_name: str
    short_name: str
    trigger: str
    contracts_health_pct: Optional[float] = None
    sell_orders_health_pct: Optional[float] = None
    sell_orders_viability_pct: Optional[float] = None
    overall_health_pct: Optional[float] = None
    understocked_contracts_count: int
    sell_gaps_count: int
    contract_targets: int = 0
    contract_fulfilled: int = 0
    sell_order_targets: int = 0
    sell_order_fulfilled: int = 0
    sell_order_viable_fulfilled: int = 0
    contracts_isk: float = 0.0
    sell_orders_isk: float = 0.0
    total_isk_on_market: float = 0.0
    contracts_synced_at: Optional[str] = None
    orders_synced_at: Optional[str] = None
    understocked_contracts: List[OpsMonitorHistoryProblemContract] = []
    sell_gaps: List[OpsMonitorHistorySellGap] = []


@router.get(
    "/ops-monitor/history",
    description=(
        "Historical staging supply health snapshots captured after market "
        "ESI syncs (contracts / structure orders). Built from local DB only."
    ),
    response=List[OpsMonitorHistoryPoint],
)
def get_ops_monitor_history(
    request,
    location_id: int | None = None,
    limit: int = 48,
):
    return list_ops_monitor_snapshots(location_id=location_id, limit=limit)
