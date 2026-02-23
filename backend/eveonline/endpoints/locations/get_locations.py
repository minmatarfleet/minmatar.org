"""GET / - fetch all locations."""

from typing import List

from ninja import Router
from pydantic import BaseModel

from eveonline.models import EveLocation

router = Router(tags=["Locations"])


class LocationResponse(BaseModel):
    location_id: int
    location_name: str
    solar_system_id: int
    solar_system_name: str
    short_name: str
    region_id: int | None = None
    market_active: bool
    prices_active: bool
    freight_active: bool
    staging_active: bool


@router.get(
    "",
    description="Fetch all locations",
    response={200: List[LocationResponse]},
)
def get_locations(request) -> List[LocationResponse]:
    locations = EveLocation.objects.all().order_by("location_name")
    return [
        LocationResponse(
            location_id=loc.location_id,
            location_name=loc.location_name,
            solar_system_id=loc.solar_system_id,
            solar_system_name=loc.solar_system_name,
            short_name=loc.short_name,
            region_id=loc.region_id,
            market_active=loc.market_active,
            prices_active=loc.prices_active,
            freight_active=loc.freight_active,
            staging_active=loc.staging_active,
        )
        for loc in locations
    ]
