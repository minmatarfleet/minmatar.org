from ninja import Router

from market.endpoints.cache import get_cached
from market.models import EveMarketContractExpectation
from market.endpoints.schemas import (
    LocationExpectationsResponse,
    LocationFittingExpectationResponse,
)

router = Router(tags=["Market"])


@router.get(
    "/expectations/by-location",
    description="Get all market contract expectations grouped by location and fitting",
    response=list[LocationExpectationsResponse],
)
@get_cached(key_suffix="expectations-by-location")
def get_expectations_by_location(
    request,
) -> list[LocationExpectationsResponse]:
    expectations = EveMarketContractExpectation.objects.select_related(
        "location", "fitting"
    ).order_by("location__location_name", "fitting__name")

    location_map = {}
    for expectation in expectations:
        location_id = expectation.location.location_id
        if location_id not in location_map:
            location_map[location_id] = {
                "location": expectation.location,
                "expectations": [],
            }
        location_map[location_id]["expectations"].append(expectation)

    return [
        LocationExpectationsResponse(
            location_id=data["location"].location_id,
            location_name=data["location"].location_name,
            solar_system_name=data["location"].solar_system_name,
            short_name=data["location"].short_name,
            expectations=[
                LocationFittingExpectationResponse(
                    fitting_id=e.fitting.id,
                    fitting_name=e.fitting.name,
                    expectation_id=e.id,
                    quantity=e.quantity,
                )
                for e in data["expectations"]
            ],
        )
        for _, data in sorted(location_map.items())
    ]
