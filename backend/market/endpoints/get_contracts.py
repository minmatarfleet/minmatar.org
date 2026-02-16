from collections import defaultdict

from django.db.models import Count, Max
from ninja import Router

from market.helpers import get_historical_quantity, entity_name_by_id
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketContractResponsibility,
)
from market.endpoints.schemas import (
    MarketContractResponse,
    MarketContractResponsibilityResponse,
    MarketContractHistoricalQuantityResponse,
)

router = Router(tags=["Market"])


@router.get(
    "/contracts",
    description="Fetch all market contracts for all characters and corporations",
    response=list[MarketContractResponse],
)
def fetch_eve_market_contracts(request):
    expectations = EveMarketContractExpectation.objects.select_related(
        "fitting", "location"
    ).all()

    all_responsibilities = list(
        EveMarketContractResponsibility.objects.filter(
            expectation__in=expectations
        )
    )
    entity_ids = {r.entity_id for r in all_responsibilities}
    entity_info = entity_name_by_id(entity_ids)
    resp_by_expectation = defaultdict(list)
    for r in all_responsibilities:
        if r.entity_id in entity_info:
            resp_by_expectation[r.expectation_id].append(r)

    outstanding_stats = {
        row["fitting_id"]: (row["count"], row["latest"])
        for row in EveMarketContract.objects.filter(status="outstanding")
        .values("fitting_id")
        .annotate(
            count=Count("id"),
            latest=Max("created_at"),
        )
    }

    response = []
    for expectation in expectations:
        responsibilities = [
            MarketContractResponsibilityResponse(
                entity_type=entity_info[r.entity_id][0],
                entity_id=r.entity_id,
                entity_name=entity_info[r.entity_id][1],
            )
            for r in resp_by_expectation[expectation.id]
        ]
        historical_quantity = get_historical_quantity(expectation)
        count, latest = outstanding_stats.get(
            expectation.fitting_id, (0, None)
        )
        response.append(
            MarketContractResponse(
                expectation_id=expectation.id,
                title=expectation.fitting.name,
                fitting_id=expectation.fitting.id,
                structure_id=None,
                location_name=expectation.location.location_name,
                desired_quantity=expectation.quantity,
                current_quantity=count,
                latest_contract_timestamp=str(latest) if latest else None,
                historical_quantity=[
                    MarketContractHistoricalQuantityResponse(
                        date=entry.date, quantity=entry.quantity
                    )
                    for entry in historical_quantity
                ],
                responsibilities=responsibilities,
            )
        )

    return response
