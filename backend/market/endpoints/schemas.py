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


class MarketContractResponsibilityResponse(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str


class MarketContractHistoricalQuantityResponse(BaseModel):
    date: str
    quantity: int


class MarketContractResponse(BaseModel):
    expectation_id: int | None = (
        None  # None when no expectation for this fitting at location
    )
    title: str
    fitting_id: int
    structure_id: int | None = None
    location_name: str
    desired_quantity: int
    current_quantity: int
    latest_contract_timestamp: str | None = None
    historical_quantity: List[MarketContractHistoricalQuantityResponse]
    responsibilities: List[MarketContractResponsibilityResponse]
    doctrines: List[MarketContractDoctrineResponse]
