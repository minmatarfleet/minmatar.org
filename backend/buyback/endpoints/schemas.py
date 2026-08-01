from typing import List, Optional

from pydantic import BaseModel, Field


class BuybackLocationResponse(BaseModel):
    location_id: int
    name: str
    short_name: str


class BuybackRateRules(BaseModel):
    ore_refine: float = Field(default=0.85, ge=0, le=1)
    ore_jita_buy: float = Field(default=1.0, ge=0, le=1)
    p1_jita_buy_cap: float = Field(default=0.9, ge=0, le=1)
    other_jita_buy: float = Field(default=1.0, ge=0, le=1)


class BuybackAppraiseRequest(BaseModel):
    paste: str = Field(..., min_length=1)


class BuybackAppraisalLine(BaseModel):
    type_id: Optional[int] = None
    name: str
    quantity: int
    category: str
    rate: Optional[float] = None
    jita_buy: Optional[float] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    accepted: bool
    reject_reason: Optional[str] = None


class BuybackAppraisalResponse(BaseModel):
    lines: List[BuybackAppraisalLine]
    offer_total: float
    accepted_count: int
    rejected_count: int
    rate_rules: BuybackRateRules


class BuybackAcceptedItemResponse(BaseModel):
    type_id: int
    name: str
    category: str


class BuybackSettingsResponse(BaseModel):
    active: bool
    assignee_name: str
    corporation_id: int
    location: Optional[BuybackLocationResponse] = None
    accepted_categories: List[str]
    accepted_items: List[BuybackAcceptedItemResponse] = []
    rate_rules: BuybackRateRules
    exclusions: List[str]
    discord_thread_url: str
    leading_text: str


class BuybackContractResponse(BaseModel):
    contract_id: int
    status: str
    location_name: str
    volume: int
    price: int
    title: str
    date_issued: str
    date_completed: Optional[str] = None
    issuer_id: Optional[int] = None
    issuer_character_name: Optional[str] = None
    acceptor_id: Optional[int] = None
    acceptor_character_name: Optional[str] = None
    updated_at: Optional[str] = None


class BuybackContractsStatsResponse(BaseModel):
    outstanding_count: int
    outstanding_isk: int
    finished_count: int
    finished_isk: int
    average_processing_seconds: Optional[int] = None
    window_days: int = 30
