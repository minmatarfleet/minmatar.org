"""Shared schemas and checks for the LP desk Settings endpoints.

Access is the ``industry.loyalty.settings`` feature (legacy permission
``industry.change_industryloyaltypoint``). Price history and the ledger stay
read-only: only the three configuration models are written here.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.errors import ErrorResponse
from eveonline.helpers.characters import user_primary_character
from groups.helpers.feature_access import can_use_feature
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointContact,
    IndustryLoyaltyPointPriceHistory,
)

FEATURE = "industry.loyalty.settings"


def can_edit_settings(user) -> bool:
    return can_use_feature(user, FEATURE)


def forbidden():
    return 403, ErrorResponse.new("LP settings permission required")


class SettingsContact(BaseModel):
    id: int
    account_id: int
    character_name: str
    discord_username: str
    notes: str
    is_active: bool


class SettingsAccount(BaseModel):
    id: int
    loyalty_point_id: int
    name: str
    role: str
    isk_per_lp: Optional[int]
    corporation_name: str
    notes: str
    is_active: bool
    contacts: list[SettingsContact]


class SettingsPriceChange(BaseModel):
    """One ISK/LP change: the corp's standard or express rate, or an account offer."""

    tier: str
    account_name: Optional[str]
    old_isk_per_lp: Optional[int]
    new_isk_per_lp: Optional[int]
    changed_at: datetime
    changed_by: Optional[str]


class SettingsCurrency(BaseModel):
    id: int
    name: str
    corporation_id: int
    default_isk_per_lp: int
    express_isk_per_lp: Optional[int]
    is_active: bool
    allow_buy: bool
    allow_sell: bool
    notes: str
    accounts: list[SettingsAccount]
    # Enabled accounts; a desk with none has nobody to sell or hold the LP.
    active_account_count: int = 0
    # The newest price change, for the "changed ... ago" line.
    last_change: Optional[SettingsPriceChange] = None


class CurrencyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    corporation_id: int
    default_isk_per_lp: int = Field(default=800, ge=0)
    express_isk_per_lp: Optional[int] = Field(default=None, ge=0)


class CurrencyPatchRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    default_isk_per_lp: Optional[int] = Field(default=None, ge=0)
    # Send ``clear_express`` to turn express off (null means "unchanged").
    express_isk_per_lp: Optional[int] = Field(default=None, ge=0)
    clear_express: bool = False
    is_active: Optional[bool] = None
    allow_buy: Optional[bool] = None
    allow_sell: Optional[bool] = None
    notes: Optional[str] = None


class AccountCreateRequest(BaseModel):
    loyalty_point_id: int
    name: str = Field(min_length=1, max_length=128)
    role: str = "seller"
    isk_per_lp: Optional[int] = Field(default=None, ge=0)
    corporation_name: str = ""
    notes: str = ""


class AccountPatchRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    role: Optional[str] = None
    isk_per_lp: Optional[int] = Field(default=None, ge=0)
    clear_isk_per_lp: bool = False
    corporation_name: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ContactCreateRequest(BaseModel):
    account_id: int
    character_name: str = Field(min_length=1, max_length=64)
    discord_username: str = ""
    notes: str = ""


class ContactPatchRequest(BaseModel):
    character_name: Optional[str] = Field(
        default=None, min_length=1, max_length=64
    )
    discord_username: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


def contact_schema(contact: IndustryLoyaltyPointContact) -> SettingsContact:
    return SettingsContact(
        id=contact.id,
        account_id=contact.account_id,
        character_name=contact.character_name,
        discord_username=contact.discord_username,
        notes=contact.notes,
        is_active=contact.is_active,
    )


def account_schema(account: IndustryLoyaltyPointAccount) -> SettingsAccount:
    return SettingsAccount(
        id=account.id,
        loyalty_point_id=account.loyalty_point_id,
        name=account.name,
        role=account.role,
        isk_per_lp=account.isk_per_lp,
        corporation_name=account.corporation_name,
        notes=account.notes,
        is_active=account.is_active,
        contacts=[contact_schema(c) for c in account.contacts.all()],
    )


def _user_name(user) -> Optional[str]:
    if user is None:
        return None
    primary = user_primary_character(user)
    return primary.character_name if primary else user.username


def price_change_schema(
    change: IndustryLoyaltyPointPriceHistory,
) -> SettingsPriceChange:
    return SettingsPriceChange(
        tier=change.tier,
        account_name=change.account.name if change.account_id else None,
        old_isk_per_lp=change.old_isk_per_lp,
        new_isk_per_lp=change.new_isk_per_lp,
        changed_at=change.changed_at,
        changed_by=_user_name(change.changed_by),
    )


def price_history(currency_id: int, limit: int = 20):
    return list(
        IndustryLoyaltyPointPriceHistory.objects.filter(
            loyalty_point_id=currency_id
        )
        .select_related("account", "changed_by")
        .order_by("-changed_at", "-id")[:limit]
    )


def currency_schema(currency: IndustryLoyaltyPoint) -> SettingsCurrency:
    # One small indexed query per corp; the desk has a handful of corps.
    newest = price_history(currency.id, limit=1)
    last_change = newest[0] if newest else None
    accounts = list(currency.accounts.all())
    return SettingsCurrency(
        id=currency.id,
        name=currency.name,
        corporation_id=currency.corporation_id,
        default_isk_per_lp=currency.default_isk_per_lp,
        express_isk_per_lp=currency.express_isk_per_lp,
        is_active=currency.is_active,
        allow_buy=currency.allow_buy,
        allow_sell=currency.allow_sell,
        notes=currency.notes,
        accounts=[account_schema(a) for a in accounts],
        active_account_count=sum(1 for a in accounts if a.is_active),
        last_change=(
            price_change_schema(last_change) if last_change else None
        ),
    )
