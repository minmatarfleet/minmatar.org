"""Shared schemas and checks for the freight route editor.

Access is the ``freight.manage`` feature (legacy permission
``freight.change_evefreightroute``).
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.errors import ErrorResponse
from freight.models import EveFreightRoute
from groups.helpers.feature_access import can_use_feature

FEATURE = "freight.manage"

# An empty editor box sends null. These are the only fields that should clear.
NULLABLE_FIELDS = frozenset({"max_m3", "max_collateral"})

FIELDS = (
    "route_type",
    "isk_per_m3",
    "collateral_modifier",
    "fixed_fee_millions",
    "xl_fee_millions",
    "max_m3",
    "max_collateral",
    "expiration_days",
    "days_to_complete",
    "active",
)


def can_manage(user) -> bool:
    return can_use_feature(user, FEATURE)


def forbidden():
    return 403, ErrorResponse.new("Freight route permission required")


class RouteLocation(BaseModel):
    location_id: int
    name: str
    short_name: str


class ManageRoute(BaseModel):
    route_id: int
    origin: Optional[RouteLocation]
    destination: Optional[RouteLocation]
    route_type: str
    isk_per_m3: int
    collateral_modifier: float
    fixed_fee_millions: float
    xl_fee_millions: float
    max_m3: Optional[int]
    max_collateral: Optional[int]
    expiration_days: int
    days_to_complete: int
    active: bool


class ManageRoutes(BaseModel):
    routes: list[ManageRoute]
    locations: list[RouteLocation]


class RouteCreateRequest(BaseModel):
    origin_location_id: int
    destination_location_id: int
    route_type: str = "rate"
    isk_per_m3: int = Field(default=0, ge=0)
    collateral_modifier: float = Field(default=0, ge=0)
    fixed_fee_millions: float = Field(default=0, ge=0)
    xl_fee_millions: float = Field(default=0, ge=0)
    max_m3: Optional[int] = Field(default=None, ge=0)
    max_collateral: Optional[int] = Field(default=None, ge=0)
    expiration_days: int = Field(default=3, ge=1)
    days_to_complete: int = Field(default=3, ge=1)
    active: bool = True


class RoutePatchRequest(BaseModel):
    route_type: Optional[str] = None
    isk_per_m3: Optional[int] = Field(default=None, ge=0)
    collateral_modifier: Optional[float] = Field(default=None, ge=0)
    fixed_fee_millions: Optional[float] = Field(default=None, ge=0)
    xl_fee_millions: Optional[float] = Field(default=None, ge=0)
    max_m3: Optional[int] = Field(default=None, ge=0)
    max_collateral: Optional[int] = Field(default=None, ge=0)
    expiration_days: Optional[int] = Field(default=None, ge=1)
    days_to_complete: Optional[int] = Field(default=None, ge=1)
    active: Optional[bool] = None


def _location(location) -> Optional[RouteLocation]:
    if location is None:
        return None
    return RouteLocation(
        location_id=location.location_id,
        name=location.location_name,
        short_name=location.short_name,
    )


def route_schema(route: EveFreightRoute) -> ManageRoute:
    return ManageRoute(
        route_id=route.id,
        origin=_location(route.origin_location),
        destination=_location(route.destination_location),
        route_type=route.route_type,
        isk_per_m3=route.isk_per_m3,
        collateral_modifier=route.collateral_modifier,
        fixed_fee_millions=route.fixed_fee_millions,
        xl_fee_millions=route.xl_fee_millions,
        max_m3=route.max_m3,
        max_collateral=route.max_collateral,
        expiration_days=route.expiration_days,
        days_to_complete=route.days_to_complete,
        active=route.active,
    )
