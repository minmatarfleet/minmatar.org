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
    freight_active: bool
    staging_active: bool


@router.get(
    "/",
    description="Fetch all locations",
    response={200: List[LocationResponse]},
)
def get_locations(request) -> List[LocationResponse]:
    """Fetch all EveLocation objects"""
    locations = EveLocation.objects.all().order_by("location_name")
    return [
        LocationResponse(
            location_id=location.location_id,
            location_name=location.location_name,
            solar_system_id=location.solar_system_id,
            solar_system_name=location.solar_system_name,
            short_name=location.short_name,
            region_id=location.region_id,
            market_active=location.market_active,
            freight_active=location.freight_active,
            staging_active=location.staging_active,
        )
        for location in locations
    ]
