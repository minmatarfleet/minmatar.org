"""Schemas for industry loyalty / LP buyback endpoints."""

from datetime import date, datetime
from typing import Optional

from ninja import Schema


class LoyaltyCurrencyResponse(Schema):
    id: int
    name: str
    corporation_id: int
    default_isk_per_lp: int
    express_isk_per_lp: Optional[int] = None
    is_active: bool
    allow_buy: bool = True
    allow_sell: bool = True


class LoyaltyCapabilitiesResponse(Schema):
    can_manage: bool
    can_trade: bool


class LoyaltyMarketOrderClaimResponse(Schema):
    id: int
    amount: int
    destination_character_name: str = ""
    destination_corporation_name: str = ""
    destination_corporation_id: Optional[int] = None
    claimed_by_user_id: Optional[int] = None
    claimed_by_name: Optional[str] = None
    claimed_by_character_id: Optional[int] = None
    created_at: datetime


class LoyaltyMarketOrderResponse(Schema):
    id: int
    loyalty_point_id: int
    loyalty_point_name: str
    corporation_id: int
    side: str
    quantity: int
    quantity_claimed: int = 0
    quantity_remaining: int = 0
    isk_per_lp: int
    tier: str = "standard"
    express_due_at: Optional[datetime] = None
    status: str
    created_by_user_id: Optional[int] = None
    created_by_name: Optional[str] = None
    created_by_character_id: Optional[int] = None
    claimed_by_user_id: Optional[int] = None
    claimed_by_name: Optional[str] = None
    claimed_by_character_id: Optional[int] = None
    destination_character_name: str = ""
    destination_corporation_id: Optional[int] = None
    discord_thread_id: Optional[int] = None
    # Only GET /orders/{id} fills this (one channel lookup per order).
    discord_thread_url: str = ""
    notes: str = ""
    claims: list[LoyaltyMarketOrderClaimResponse] = []
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class LoyaltyMarketOrdersListResponse(Schema):
    items: list[LoyaltyMarketOrderResponse]
    total: int
    limit: Optional[int] = None
    offset: int = 0


class CreateLoyaltyMarketOrderRequest(Schema):
    loyalty_point_id: int
    side: str
    quantity: int
    isk_per_lp: Optional[int] = None
    tier: str = "standard"
    destination_character_name: str = ""
    notes: str = ""


class ClaimLoyaltyMarketOrderRequest(Schema):
    amount: Optional[int] = None
    destination_character_name: str = ""
    destination_corporation_name: str = ""


class PatchLoyaltyMarketOrderRequest(Schema):
    status: Optional[str] = None
    destination_character_name: Optional[str] = None
    notes: Optional[str] = None


class DiscordAckLoyaltyMarketOrderRequest(Schema):
    discord_user_id: int
    action: str


class LoyaltyOrderStatsTier(Schema):
    orders: int
    completed: int
    avg_close_seconds: Optional[int] = None
    median_close_seconds: Optional[int] = None
    paid_within_day: int = 0
    lp_completed: int = 0
    isk_completed: int = 0
    avg_isk_per_lp: Optional[float] = None


class LoyaltyOrderStatsWeek(Schema):
    week_start: date
    lp: int


class LoyaltyOrderStatsConverter(Schema):
    user_id: int
    name: str
    character_id: Optional[int] = None
    orders: int
    lp: int
    isk: int
    median_settle_seconds: Optional[int] = None


class LoyaltyOrderStatsResponse(LoyaltyOrderStatsTier):
    days: int
    median_claim_seconds: Optional[int] = None
    median_settle_seconds: Optional[int] = None
    standard: LoyaltyOrderStatsTier
    express: LoyaltyOrderStatsTier
    weekly: list[LoyaltyOrderStatsWeek] = []
    converters: list[LoyaltyOrderStatsConverter] = []


class LoyaltyLedgerEntryResponse(Schema):
    id: int
    account_id: int
    account_name: str
    account_role: str
    loyalty_point_id: int
    loyalty_point_name: str
    corporation_id: int
    amount: int
    isk_per_lp: int
    balance_after: int
    notes: str = ""
    market_order_id: Optional[int] = None
    seller_user_id: Optional[int] = None
    seller_character_name: str = ""
    counterparty_user_id: Optional[int] = None
    counterparty_character_name: str = ""
    created_by_user_id: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: datetime


class LoyaltyOfferConversionCosts(Schema):
    """Per-LP costs inside one side's net conversion (plan_costing defaults)."""

    sales_tax_isk_per_lp: Optional[float] = None
    input_freight_isk_per_lp: Optional[float] = None
    output_freight_isk_per_lp: Optional[float] = None


class LoyaltyOfferResponse(Schema):
    offer_id: int
    corporation_id: int
    type_id: int
    type_name: str
    currency_name: str
    lp_cost: int
    isk_cost: int
    ak_cost: int
    quantity: int
    required_items_summary: str
    other_cost: Optional[int] = None
    input_cost_isk: Optional[int] = None
    input_freight_isk: Optional[int] = None
    jita_sell: Optional[int] = None
    jita_buy: Optional[int] = None
    jita_avg_7d: Optional[int] = None
    conversion_isk_per_lp_sell: Optional[float] = None
    conversion_isk_per_lp_buy: Optional[float] = None
    conversion_isk_per_lp_avg_7d: Optional[float] = None
    # Keyed by side: "sell", "buy", "avg_7d".
    conversion_costs: dict[str, LoyaltyOfferConversionCosts] = {}
    volume_1d: Optional[int] = None
    volume_7d: Optional[int] = None
    volume_30d: Optional[int] = None
    kind: str = ""
    updated_at: datetime


class LoyaltyOffersListResponse(Schema):
    items: list[LoyaltyOfferResponse]
    total: int
    limit: int
    offset: int
    rebuilt_at: Optional[datetime] = None
