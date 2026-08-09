from typing import Any, List, Optional

from ninja import Schema


class HealthSummaryFields(Schema):
    health_pct: Optional[float] = None
    viability_pct: Optional[float] = None
    targets: int = 0
    fulfilled: int = 0
    viable_fulfilled: int = 0
    isk: float = 0.0
    synced_at: Optional[str] = None
    history_days: int = 0


class HealthLatest(HealthSummaryFields):
    id: int
    captured_at: str
    location_id: int
    location_name: str
    short_name: str


class HealthHistoryPoint(HealthSummaryFields):
    id: int
    captured_at: str


class KindHealthResponse(Schema):
    latest: Optional[HealthLatest] = None
    history: List[HealthHistoryPoint] = []


class MarketHealthChartPoint(Schema):
    captured_at: str
    contracts_health_pct: Optional[float] = None
    contracts_viability_pct: Optional[float] = None
    sell_orders_health_pct: Optional[float] = None
    sell_orders_viability_pct: Optional[float] = None


class MarketHealthResponse(Schema):
    contracts: KindHealthResponse
    sell_orders: KindHealthResponse
    chart: List[MarketHealthChartPoint] = []


class LiveSellOrderSupplyResponse(HealthSummaryFields):
    location_id: int
    rows: List[Any] = []
