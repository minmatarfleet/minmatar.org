"""Shared schemas and checks for the LP desk Settings endpoints.

Access is the ``industry.loyalty.settings`` feature (legacy permission
``industry.change_industryloyaltypoint``). Price history and the ledger stay
read-only: only the three configuration models are written here.
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.errors import ErrorResponse
from groups.helpers.feature_access import can_use_feature
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointContact,
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


def currency_schema(currency: IndustryLoyaltyPoint) -> SettingsCurrency:
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
        accounts=[account_schema(a) for a in currency.accounts.all()],
    )
