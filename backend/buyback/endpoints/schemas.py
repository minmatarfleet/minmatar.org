from typing import List, Optional

from pydantic import BaseModel, Field


class BuybackLocationResponse(BaseModel):
    location_id: int
    name: str
    short_name: str


class BuybackRateRules(BaseModel):
    ore_refine: float = Field(default=0.85, ge=0, le=1)
    demand_jita_buy: float = Field(default=1.0, ge=0, le=1)
    surplus_jita_buy: float = Field(default=0.9, ge=0, le=1)


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
    rate_reason: Optional[str] = None


class BuybackAppraisalResponse(BaseModel):
    lines: List[BuybackAppraisalLine]
    offer_total: float
    accepted_count: int
    rejected_count: int
    rate_rules: BuybackRateRules


class BuybackUsedInProduct(BaseModel):
    type_id: int
    name: str


class BuybackAcceptedItemResponse(BaseModel):
    type_id: int
    name: str
    category: str
    used_in: List[BuybackUsedInProduct] = []
    in_demand: bool = False
    demand_status: str = "surplus"
    demand_quantity: int = 0
    stockpile_quantity: int = 0


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


class BuybackOnHandItem(BaseModel):
    type_id: int
    name: str
    category: Optional[str] = None
    quantity: int
    demand_status: Optional[str] = None
    isk_value: Optional[float] = None


class BuybackOnHandResponse(BaseModel):
    items: List[BuybackOnHandItem]
    updated_at: Optional[str] = None


class BuybackStockStatsResponse(BaseModel):
    stockpile_value: int
    remaining_isk: Optional[int] = None
    turnover_value: int
    window_days: int = 30


class BuybackLedgerEntryResponse(BaseModel):
    id: int
    reason: str
    type_id: int
    name: str
    quantity: int
    occurred_at: str
    unit_price: Optional[float] = None
    isk_total: Optional[float] = None
    isk_value: Optional[float] = None
    source_id: str
    location_id: Optional[int] = None
    counterparty_id: Optional[int] = None
    counterparty_name: Optional[str] = None
    counterparty_kind: Optional[str] = None


class BuybackLedgerResponse(BaseModel):
    entries: List[BuybackLedgerEntryResponse]
    count: int


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
