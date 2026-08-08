"""Deferred volume / fleet metrics for market contracts."""

from django.db.models import Count
from ninja import Router

from eveonline.models import EveLocation

from market.endpoints.cache import get_cached
from market.endpoints.schemas import MarketContractMetricsResponse
from market.helpers import finished_contract_volume_by_fitting
from market.helpers.contract_fleet_demand import fleet_demand_by_fitting
from market.helpers.contract_stock import outstanding_stock_q
from market.helpers.contracts import fleets_remaining_from_stock
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
)

router = Router(tags=["Market"])


@router.get(
    "/contracts/metrics",
    description=(
        "Finished volume and doctrine fleet demand metrics for contracts "
        "at a location. Intended to load after the main contracts list."
    ),
    response=list[MarketContractMetricsResponse],
)
@get_cached(
    key_suffix=lambda req, location_id: f"contracts-metrics:{location_id}"
)
def fetch_eve_market_contract_metrics(request, location_id: int):
    try:
        location = EveLocation.objects.get(location_id=location_id)
    except EveLocation.DoesNotExist:
        return []

    contracts_at_location = EveMarketContract.objects.filter(
        location=location, fitting_id__isnull=False
    )
    fitting_ids = set(
        contracts_at_location.values_list("fitting_id", flat=True).distinct()
    )
    fitting_ids |= set(
        EveMarketContractExpectation.objects.filter(
            location=location
        ).values_list("fitting_id", flat=True)
    )
    if not fitting_ids:
        return []

    outstanding_counts = {
        row["fitting_id"]: row["count"]
        for row in contracts_at_location.filter(outstanding_stock_q())
        .values("fitting_id")
        .annotate(count=Count("id"))
    }

    volume_by_fitting = finished_contract_volume_by_fitting(
        location=location,
        fitting_ids=fitting_ids,
    )
    fleet_demand_by_fit = fleet_demand_by_fitting(
        fitting_ids=fitting_ids,
        location=location,
    )

    response: list[MarketContractMetricsResponse] = []
    for fitting_id in fitting_ids:
        fleet_demand = fleet_demand_by_fit.get(fitting_id)
        typical_fleet_size = (
            fleet_demand.typical_fleet_size if fleet_demand else None
        )
        fleets_per_month = (
            fleet_demand.fleets_per_month if fleet_demand else None
        )
        current = outstanding_counts.get(fitting_id, 0)
        response.append(
            MarketContractMetricsResponse(
                fitting_id=fitting_id,
                volume_28d=volume_by_fitting.get(fitting_id, 0),
                typical_fleet_size=typical_fleet_size,
                fleets_remaining=fleets_remaining_from_stock(
                    current, typical_fleet_size
                ),
                fleets_per_month=fleets_per_month,
            )
        )

    response.sort(key=lambda row: row.fitting_id)
    return response
