from collections import defaultdict

from django.db.models import Count, Max
from ninja import Router

from eveonline.models import EveCharacter, EveLocation
from fittings.models import EveDoctrineFitting

from market.endpoints.cache import get_cached
from market.endpoints.schemas import (
    MarketContractDoctrineResponse,
    MarketContractHistoricalQuantityResponse,
    MarketContractResponse,
    MarketContractSellerResponse,
)
from market.helpers import (
    get_historical_quantity_for_fitting,
)
from market.helpers.contract_stock import outstanding_stock_q
from market.helpers.readiness import fitting_readiness
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
)

router = Router(tags=["Market"])


def _stock_sort_key(row: MarketContractResponse) -> tuple:
    """100% stock first, then down to 0%; no-expectation rows last."""
    if row.desired_quantity <= 0:
        return (1, 0.0, row.title)
    fill = row.current_quantity / row.desired_quantity
    return (0, -fill, row.title)


@router.get(
    "/contracts",
    description="Fetch all market contracts for a location (all EveMarketContracts at that location)",
    response=list[MarketContractResponse],
)
@get_cached(key_suffix=lambda req, location_id: f"contracts:{location_id}")
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

    outstanding = contracts_at_location.filter(outstanding_stock_q())

    # Outstanding contract stats per fitting at this location (verified stock)
    outstanding_stats = {
        row["fitting_id"]: (row["count"], row["latest"])
        for row in outstanding.values("fitting_id").annotate(
            count=Count("id"),
            latest=Max("created_at"),
        )
    }

    # Sellers (issuers) per fitting with outstanding stock counts
    sellers_by_fitting: dict[int, list[tuple[int, int]]] = defaultdict(list)
    all_issuer_ids: set[int] = set()
    for row in (
        outstanding.values("fitting_id", "issuer_external_id")
        .annotate(quantity=Count("id"))
        .order_by("-quantity")
    ):
        issuer_id = int(row["issuer_external_id"])
        all_issuer_ids.add(issuer_id)
        sellers_by_fitting[row["fitting_id"]].append(
            (issuer_id, row["quantity"])
        )

    character_names = dict(
        EveCharacter.objects.filter(
            character_id__in=all_issuer_ids
        ).values_list("character_id", "character_name")
    )

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
    for fitting_id in all_fitting_ids:
        expectation = expectation_by_fitting.get(fitting_id)
        if expectation is not None:
            fitting = expectation.fitting
            expectation_id = expectation.id
            title = fitting.name
            desired_quantity = expectation.quantity
        else:
            # Fitting has contracts but no expectation; load fitting from a contract
            sample = (
                contracts_at_location.filter(fitting_id=fitting_id)
                .select_related("fitting")
                .first()
            )
            fitting = sample.fitting
            expectation_id = None
            title = fitting.name
            desired_quantity = 0

        count, latest = outstanding_stats.get(fitting_id, (0, None))
        readiness = fitting_readiness(count, desired_quantity or None)
        historical_quantity = get_historical_quantity_for_fitting(
            fitting, location=location
        )
        sellers = [
            MarketContractSellerResponse(
                character_id=issuer_id,
                character_name=character_names.get(issuer_id, str(issuer_id)),
                quantity=quantity,
            )
            for issuer_id, quantity in sellers_by_fitting.get(fitting_id, [])
        ]

        response.append(
            MarketContractResponse(
                expectation_id=expectation_id,
                title=title,
                fitting_id=fitting_id,
                ship_id=fitting.ship_id,
                structure_id=None,
                location_id=location.location_id,
                location_name=location.location_name,
                desired_quantity=desired_quantity,
                current_quantity=count,
                readiness=readiness,
                sellers=sellers,
                latest_contract_timestamp=str(latest) if latest else None,
                historical_quantity=[
                    MarketContractHistoricalQuantityResponse(
                        date=entry.date, quantity=entry.quantity
                    )
                    for entry in historical_quantity
                ],
                doctrines=doctrines_by_fitting.get(fitting_id, []),
            )
        )

    response.sort(key=_stock_sort_key)

    return response
