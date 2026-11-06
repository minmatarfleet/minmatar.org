"""Shared schemas and checks for the buyback Settings endpoints.

Access is the ``buyback.manage`` feature (legacy permission
``buyback.change_evebuybacksettings``). Snapshots and the ledger stay
read-only.
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.errors import ErrorResponse
from buyback.models import BuybackAcceptedItem, EveBuybackSettings
from eveonline.models import EveLocation
from groups.helpers.feature_access import can_use_feature

FEATURE = "buyback.manage"


def can_manage(user) -> bool:
    return can_use_feature(user, FEATURE)


def forbidden():
    return 403, ErrorResponse.new("Buyback settings permission required")


class LocationOption(BaseModel):
    location_id: int
    name: str


class ManageItem(BaseModel):
    type_id: int
    name: str
    category: str
    active: bool


class ManageSettings(BaseModel):
    active: bool
    location_id: Optional[int]
    ore_refine: float
    demand_jita_buy: float
    surplus_jita_buy: float
    locations: list[LocationOption]
    categories: list[str]
    items: list[ManageItem]


class SettingsPatchRequest(BaseModel):
    active: Optional[bool] = None
    location_id: Optional[int] = None
    clear_location: bool = False
    ore_refine: Optional[float] = Field(default=None, ge=0, le=1)
    demand_jita_buy: Optional[float] = Field(default=None, ge=0, le=1)
    surplus_jita_buy: Optional[float] = Field(default=None, ge=0, le=1)


class ItemCreateRequest(BaseModel):
    type_id: int
    category: str


class ItemPatchRequest(BaseModel):
    active: Optional[bool] = None
    category: Optional[str] = None


class TypeRow(BaseModel):
    type_id: int
    name: str


def item_schema(item: BuybackAcceptedItem) -> ManageItem:
    return ManageItem(
        type_id=item.eve_type_id,
        name=item.eve_type.name,
        category=item.category,
        active=item.active,
    )


def settings_schema() -> ManageSettings:
    settings = EveBuybackSettings.load()
    items = BuybackAcceptedItem.objects.select_related("eve_type").order_by(
        "category", "eve_type__name"
    )
    return ManageSettings(
        active=settings.active,
        location_id=settings.location_id,
        ore_refine=settings.ore_refine,
        demand_jita_buy=settings.demand_jita_buy,
        surplus_jita_buy=settings.surplus_jita_buy,
        locations=[
            LocationOption(location_id=loc.location_id, name=loc.location_name)
            for loc in EveLocation.objects.order_by("location_name")
        ],
        categories=list(BuybackAcceptedItem.Category.values),
        items=[item_schema(i) for i in items],
    )
