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
    category_label: str = ""
    demand_status: str = ""
    demand_label: str = ""
    # Share of Jita buy paid now: the in-demand or surplus rate by the
    # item's demand status, or null when the item is not accepted.
    pays_rate: Optional[float] = None


class ManageSettings(BaseModel):
    active: bool
    location_id: Optional[int]
    location_name: Optional[str] = None
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
    # Empty: taken from the item's market group (ore, P1-P4).
    category: str = ""


class ItemPatchRequest(BaseModel):
    active: Optional[bool] = None
    category: Optional[str] = None


class TypeRow(BaseModel):
    type_id: int
    name: str


# EVE inventory ids: the Asteroid category, and the planetary commodity tiers.
ASTEROID_CATEGORY_ID = 25
PLANETARY_GROUP_CATEGORIES = {
    1042: BuybackAcceptedItem.Category.P1,  # Basic Commodities
    1034: BuybackAcceptedItem.Category.P2,  # Refined Commodities
    1040: BuybackAcceptedItem.Category.P3,  # Specialized Commodities
    1041: BuybackAcceptedItem.Category.P4,  # Advanced Commodities
}


def infer_category(eve_type) -> Optional[str]:
    """The buyback category an item belongs in, or None when it fits none."""
    group = getattr(eve_type, "eve_group", None)
    if group is None:
        return None
    if group.id in PLANETARY_GROUP_CATEGORIES:
        return PLANETARY_GROUP_CATEGORIES[group.id]
    if group.eve_category_id == ASTEROID_CATEGORY_ID:
        return BuybackAcceptedItem.Category.ORE
    return None


def pays_rate(item: BuybackAcceptedItem, settings) -> Optional[float]:
    if not item.active:
        return None
    if item.in_demand:
        return float(settings.demand_jita_buy)
    return float(settings.surplus_jita_buy)


def item_schema(item: BuybackAcceptedItem, settings=None) -> ManageItem:
    settings = settings or EveBuybackSettings.load()
    return ManageItem(
        type_id=item.eve_type_id,
        name=item.eve_type.name,
        category=item.category,
        active=item.active,
        category_label=item.get_category_display(),
        demand_status=item.demand_status,
        demand_label=item.get_demand_status_display(),
        pays_rate=pays_rate(item, settings),
    )


def settings_schema() -> ManageSettings:
    settings = EveBuybackSettings.load()
    items = BuybackAcceptedItem.objects.select_related("eve_type").order_by(
        "category", "eve_type__name"
    )
    return ManageSettings(
        active=settings.active,
        location_id=settings.location_id,
        location_name=(
            settings.location.location_name if settings.location else None
        ),
        ore_refine=settings.ore_refine,
        demand_jita_buy=settings.demand_jita_buy,
        surplus_jita_buy=settings.surplus_jita_buy,
        locations=[
            LocationOption(location_id=loc.location_id, name=loc.location_name)
            for loc in EveLocation.objects.order_by("location_name")
        ],
        categories=list(BuybackAcceptedItem.Category.values),
        items=[item_schema(i, settings) for i in items],
    )
