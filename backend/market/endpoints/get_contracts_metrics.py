"""Deferred volume / stock-coverage metrics for market contracts."""

from ninja import Router

from eveonline.models import EveLocation

from market.endpoints.cache import get_cached
from market.endpoints.schemas import MarketContractMetricsResponse
from market.helpers.contracts import (
    finished_contract_volume_windows_by_fitting,
    unstocked_pct_by_fitting,
)
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
)

router = Router(tags=["Market"])


@router.get(
    "/contracts/metrics",
    description=(
        "Finished volume windows and 30d unstocked time for contracts "
        "at a location. Intended to load after the main contracts list."
    ),
    response=list[MarketContractMetricsResponse],
)
@get_cached(
    key_suffix=lambda req, location_id: f"contracts-metrics:v2:{location_id}"
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

    volume_by_fitting = finished_contract_volume_windows_by_fitting(
        location=location,
        fitting_ids=fitting_ids,
    )
    unstocked_by_fitting = unstocked_pct_by_fitting(
        location=location,
        fitting_ids=fitting_ids,
    )

    response: list[MarketContractMetricsResponse] = []
    for fitting_id in fitting_ids:
        windows = volume_by_fitting.get(fitting_id, {})
        response.append(
            MarketContractMetricsResponse(
                fitting_id=fitting_id,
                volume_7d=windows.get(7, 0),
                volume_30d=windows.get(30, 0),
                volume_90d=windows.get(90, 0),
                volume_365d=windows.get(365, 0),
                unstocked_pct_30d=unstocked_by_fitting.get(fitting_id, 100),
            )
        )

    response.sort(key=lambda row: row.fitting_id)
    return response
