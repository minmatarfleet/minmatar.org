"""Schemas for industry loyalty / LP buyback endpoints."""

from datetime import datetime
from typing import Optional

from ninja import Schema


class LoyaltyCurrencyResponse(Schema):
    id: int
    name: str
    corporation_id: int
    default_isk_per_lp: int
    is_active: bool


class LoyaltyMarketOrderClaimResponse(Schema):
    id: int
    amount: int
    destination_character_name: str = ""
    destination_corporation_name: str = ""
    claimed_by_user_id: int
    claimed_by_name: str
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
    status: str
    created_by_user_id: int
    created_by_name: str
    created_by_character_id: Optional[int] = None
    claimed_by_user_id: Optional[int] = None
    claimed_by_name: Optional[str] = None
    claimed_by_character_id: Optional[int] = None
    destination_character_name: str = ""
    discord_thread_id: Optional[int] = None
    notes: str = ""
    claims: list[LoyaltyMarketOrderClaimResponse] = []
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class CreateLoyaltyMarketOrderRequest(Schema):
    loyalty_point_id: int
    side: str
    quantity: int
    isk_per_lp: Optional[int] = None
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
