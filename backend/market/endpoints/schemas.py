from typing import List

from pydantic import BaseModel


class MarketContractDoctrineResponse(BaseModel):
    """Doctrine that includes this fitting (for market contract response)."""

    id: int
    name: str
    type: str
    role: str  # primary, secondary, support


class LocationFittingExpectationResponse(BaseModel):
    fitting_id: int
    fitting_name: str
    expectation_id: int
    quantity: int


class LocationExpectationsResponse(BaseModel):
    location_id: int
    location_name: str
    solar_system_name: str
    short_name: str
    expectations: List[LocationFittingExpectationResponse]


class MarketContractHistoricalQuantityResponse(BaseModel):
    date: str
    quantity: int


class MarketContractSellerResponse(BaseModel):
    character_id: int | None = None
    character_name: str | None = None
    corporation_id: int | None = None
    corporation_name: str | None = None
    quantity: int


class MarketContractMetricsResponse(BaseModel):
    """Deferred finished-volume and stock-coverage metrics for one fitting."""

    fitting_id: int
    volume_7d: int = 0
    volume_30d: int = 0
    volume_90d: int = 0
    volume_365d: int = 0
    unstocked_pct_30d: int = 100


class MarketContractResponse(BaseModel):
    expectation_id: int | None = (
        None  # None when no expectation for this fitting at location
    )
    title: str
    fitting_id: int
    ship_id: int
    structure_id: int | None = None
    location_id: int
    location_name: str
    desired_quantity: int
    current_quantity: int
    readiness: str
    sellers: List[MarketContractSellerResponse]
    latest_contract_timestamp: str | None = None
    doctrines: List[MarketContractDoctrineResponse]
