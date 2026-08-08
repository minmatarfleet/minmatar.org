from collections import defaultdict

from django.db.models import Count, Max
from ninja import Router

from eveonline.models import (
    EveCharacter,
    EveCharacterContract,
    EveCorporation,
    EveCorporationContract,
    EveLocation,
)
from fittings.models import EveDoctrineFitting

from market.endpoints.cache import get_cached
from market.endpoints.schemas import (
    MarketContractDoctrineResponse,
    MarketContractResponse,
    MarketContractSellerResponse,
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


def _corp_ids_from_source_contracts(
    contract_ids: list[int],
) -> dict[int, int]:
    """Map market contract id → issuer_corporation_id from ESI source rows."""
    if not contract_ids:
        return {}
    corp_by_contract: dict[int, int] = {}
    for model in (EveCharacterContract, EveCorporationContract):
        for contract_id, corp_id in model.objects.filter(
            contract_id__in=contract_ids,
            for_corporation=True,
            issuer_corporation_id__isnull=False,
        ).values_list("contract_id", "issuer_corporation_id"):
            corp_by_contract[int(contract_id)] = int(corp_id)
    return corp_by_contract


def _sellers_by_fitting(
    outstanding,
) -> dict[int, list[MarketContractSellerResponse]]:
    """Aggregate outstanding sellers: corp listings collapse to corporation."""
    rows = list(
        outstanding.values(
            "id",
            "fitting_id",
            "issuer_external_id",
            "issuer_corporation_id",
        )
    )
    if not rows:
        return {}

    missing_corp_lookup = [
        int(row["id"]) for row in rows if row["issuer_corporation_id"] is None
    ]
    corp_from_source = _corp_ids_from_source_contracts(missing_corp_lookup)

    counts: dict[int, dict[tuple[str, int], int]] = defaultdict(
        lambda: defaultdict(int)
    )
    character_ids: set[int] = set()
    corporation_ids: set[int] = set()

    for row in rows:
        fitting_id = row["fitting_id"]
        issuer_id = int(row["issuer_external_id"])
        corp_id = row["issuer_corporation_id"]
        if corp_id is None:
            corp_id = corp_from_source.get(int(row["id"]))
        if corp_id is not None:
            key = ("corporation", int(corp_id))
            corporation_ids.add(int(corp_id))
        else:
            key = ("character", issuer_id)
            character_ids.add(issuer_id)
        counts[fitting_id][key] += 1

    character_names = dict(
        EveCharacter.objects.filter(
            character_id__in=character_ids
        ).values_list("character_id", "character_name")
    )
    corporation_names = dict(
        EveCorporation.objects.filter(
            corporation_id__in=corporation_ids
        ).values_list("corporation_id", "name")
    )

    sellers_by_fitting: dict[int, list[MarketContractSellerResponse]] = {}
    for fitting_id, by_key in counts.items():
        sellers = []
        for (kind, entity_id), quantity in sorted(
            by_key.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        ):
            if kind == "corporation":
                sellers.append(
                    MarketContractSellerResponse(
                        corporation_id=entity_id,
                        corporation_name=corporation_names.get(
                            entity_id, str(entity_id)
                        ),
                        quantity=quantity,
                    )
                )
            else:
                sellers.append(
                    MarketContractSellerResponse(
                        character_id=entity_id,
                        character_name=character_names.get(
                            entity_id, str(entity_id)
                        ),
                        quantity=quantity,
                    )
                )
        sellers_by_fitting[fitting_id] = sellers
    return sellers_by_fitting


@router.get(
    "/contracts",
    description=(
        "Fetch market contracts for a location (stock, sellers, doctrines). "
        "Volume and fleet metrics are on GET /contracts/metrics."
    ),
    response=list[MarketContractResponse],
)
@get_cached(key_suffix=lambda req, location_id: f"contracts:{location_id}")
def fetch_eve_market_contracts(request, location_id: int):
    try:
        location = EveLocation.objects.get(location_id=location_id)
    except EveLocation.DoesNotExist:
        return []

    contracts_at_location = EveMarketContract.objects.filter(
        location=location, fitting_id__isnull=False
    )
    fitting_ids_from_contracts = set(
        contracts_at_location.values_list("fitting_id", flat=True).distinct()
    )

    expectations = EveMarketContractExpectation.objects.filter(
        location=location
    ).select_related("fitting", "location")
    expectation_by_fitting = {e.fitting_id: e for e in expectations}
    fitting_ids_from_expectations = set(expectation_by_fitting.keys())

    all_fitting_ids = (
        fitting_ids_from_contracts | fitting_ids_from_expectations
    )
    if not all_fitting_ids:
        return []

    outstanding = contracts_at_location.filter(outstanding_stock_q())

    outstanding_stats = {
        row["fitting_id"]: (row["count"], row["latest"])
        for row in outstanding.values("fitting_id").annotate(
            count=Count("id"),
            latest=Max("created_at"),
        )
    }

    sellers_by_fitting = _sellers_by_fitting(outstanding)

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
                sellers=sellers_by_fitting.get(fitting_id, []),
                latest_contract_timestamp=str(latest) if latest else None,
                doctrines=doctrines_by_fitting.get(fitting_id, []),
            )
        )

    response.sort(key=_stock_sort_key)

    return response
