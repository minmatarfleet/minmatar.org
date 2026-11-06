"""Schemas for the market hub editor."""

from typing import Optional

from pydantic import BaseModel


class HubResponse(BaseModel):
    location_id: int
    location_name: str
    short_name: str
    solar_system_name: str
    market_active: bool
    prices_active: bool
    price_baseline: bool
    fitting_expectations: int
    contract_expectations: int
    item_expectations: int


class HubCreateRequest(BaseModel):
    location_id: int
    location_name: Optional[str] = None
    short_name: Optional[str] = None
    solar_system_id: Optional[int] = None
    solar_system_name: Optional[str] = None
    region_id: Optional[int] = None
    is_structure: bool = True


class HubPatchRequest(BaseModel):
    market_active: Optional[bool] = None
    prices_active: Optional[bool] = None


class TrackedRequest(BaseModel):
    tracked: bool


class ItemExpectationRequest(BaseModel):
    type_id: int


class FromDoctrineRequest(BaseModel):
    doctrine_id: int


class FromDoctrineResponse(BaseModel):
    created: int
    already_tracked: int


class FittingExpectationRow(BaseModel):
    fitting_id: int
    fitting_name: str
    tracked: bool
    current: Optional[int] = None


class ItemExpectationRow(BaseModel):
    type_id: int
    name: str


class DoctrineOption(BaseModel):
    id: int
    name: str


class HubExpectationsResponse(BaseModel):
    location_id: int
    fittings: list[FittingExpectationRow]
    contracts: list[FittingExpectationRow]
    items: list[ItemExpectationRow]
    doctrines: list[DoctrineOption]


class TypeSearchRow(BaseModel):
    type_id: int
    name: str
