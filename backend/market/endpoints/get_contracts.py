from collections import defaultdict

from django.db.models import Count, Max
from ninja import Router

from eveonline.models import EveLocation
from fittings.models import EveDoctrineFitting

from market.helpers import (
    get_historical_quantity_for_fitting,
    entity_name_by_id,
)
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketContractResponsibility,
)
from market.endpoints.schemas import (
    MarketContractResponse,
    MarketContractResponsibilityResponse,
    MarketContractHistoricalQuantityResponse,
    MarketContractDoctrineResponse,
)

router = Router(tags=["Market"])


@router.get(
    "/contracts",
    description="Fetch all market contracts for a location (all EveMarketContracts at that location)",
    response=list[MarketContractResponse],
)
def fetch_eve_market_contracts(request, location_id: int):
    try:
        location = EveLocation.objects.get(location_id=location_id)
    except EveLocation.DoesNotExist:
        return []

    # All contracts at this location (with a fitting)
    contracts_at_location = EveMarketContract.objects.filter(
        location=location, fitting_id__isnull=False
    )
    # Distinct fitting IDs from contracts
    fitting_ids_from_contracts = set(
        contracts_at_location.values_list("fitting_id", flat=True).distinct()
    )

    # Expectations at this location
    expectations = EveMarketContractExpectation.objects.filter(
        location=location
    ).select_related("fitting", "location")
    expectation_by_fitting = {e.fitting_id: e for e in expectations}
    fitting_ids_from_expectations = set(expectation_by_fitting.keys())

    # All fittings we need to report: have contracts and/or an expectation
    all_fitting_ids = (
        fitting_ids_from_contracts | fitting_ids_from_expectations
    )
    if not all_fitting_ids:
        return []

    # Outstanding contract stats per fitting at this location
    outstanding_stats = {
        row["fitting_id"]: (row["count"], row["latest"])
        for row in contracts_at_location.filter(status="outstanding")
        .values("fitting_id")
        .annotate(
            count=Count("id"),
            latest=Max("created_at"),
        )
    }

    # Responsibilities only for expectations we have
    expectation_ids = [e.id for e in expectations]
    all_responsibilities = list(
        EveMarketContractResponsibility.objects.filter(
            expectation_id__in=expectation_ids
        )
    )
    entity_ids = {r.entity_id for r in all_responsibilities}
    entity_info = entity_name_by_id(entity_ids)
    resp_by_expectation = defaultdict(list)
    for r in all_responsibilities:
        if r.entity_id in entity_info:
            resp_by_expectation[r.expectation_id].append(r)

    # Doctrines per fitting: EveDoctrineFitting for each fitting
    doctrine_fittings = EveDoctrineFitting.objects.filter(
        fitting_id__in=all_fitting_ids
    ).select_related("doctrine", "fitting")
    doctrines_by_fitting = defaultdict(list)
    for df in doctrine_fittings:
        doctrines_by_fitting[df.fitting_id].append(
            MarketContractDoctrineResponse(
                id=df.doctrine.id,
                name=df.doctrine.name,
                type=df.doctrine.type,
                role=df.role,
            )
        )

    response = []
    for fitting_id in sorted(all_fitting_ids):
        expectation = expectation_by_fitting.get(fitting_id)
        if expectation is not None:
            fitting = expectation.fitting
            expectation_id = expectation.id
            title = fitting.name
            desired_quantity = expectation.quantity
            responsibilities = [
                MarketContractResponsibilityResponse(
                    entity_type=entity_info[r.entity_id][0],
                    entity_id=r.entity_id,
                    entity_name=entity_info[r.entity_id][1],
                )
                for r in resp_by_expectation[expectation.id]
            ]
        else:
            # Fitting has contracts but no expectation; load fitting from a contract
            sample = contracts_at_location.filter(
                fitting_id=fitting_id
            ).first()
            fitting = sample.fitting
            expectation_id = None
            title = fitting.name
            desired_quantity = 0
            responsibilities = []

        count, latest = outstanding_stats.get(fitting_id, (0, None))
        historical_quantity = get_historical_quantity_for_fitting(
            fitting, location=location
        )

        response.append(
            MarketContractResponse(
                expectation_id=expectation_id,
                title=title,
                fitting_id=fitting_id,
                structure_id=None,
                location_name=location.location_name,
                desired_quantity=desired_quantity,
                current_quantity=count,
                latest_contract_timestamp=str(latest) if latest else None,
                historical_quantity=[
                    MarketContractHistoricalQuantityResponse(
                        date=entry.date, quantity=entry.quantity
                    )
                    for entry in historical_quantity
                ],
                responsibilities=responsibilities,
                doctrines=doctrines_by_fitting.get(fitting_id, []),
            )
        )

    return response
