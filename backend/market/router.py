import logging
from collections import defaultdict
from typing import List, Optional

from django.db.models import Count, Q, Max
from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from eveonline.scopes import MARKET_SCOPES
from market.helpers import (
    MarketContractHistoricalQuantity,
    get_historical_quantity,
)
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketContractResponsibility,
    EveMarketContractError,
)

logger = logging.getLogger(__name__)
router = Router(tags=["Market"])


class CreateEveMarketContractReponsibilityRequest(BaseModel):
    expectation_id: int
    entity_id: int


class CreateEveMarketContractReponsibilityResponse(BaseModel):
    responsibility_id: int
    entity_id: int


class MarketExpectationResponse(BaseModel):
    expectation_id: int
    fitting_id: int
    fitting_name: str
    location_id: int
    location_name: str
    quantity: int


class LocationFittingExpectationResponse(BaseModel):
    """Expectation for a fitting at a location"""

    fitting_id: int
    fitting_name: str
    expectation_id: int
    quantity: int


class LocationExpectationsResponse(BaseModel):
    """Location with its fitting expectations"""

    location_id: int
    location_name: str
    solar_system_name: str
    short_name: str
    expectations: List[LocationFittingExpectationResponse]


class MarketCharacterResponse(BaseModel):
    character_id: int
    character_name: str


class MarketCorporationResponse(BaseModel):
    corporation_id: int
    corporation_name: str


class MarketContractResponsibilityResponse(BaseModel):
    entity_type: str
    entity_id: int
    entity_name: str


class MarketContractHistoricalQuantityResponse(BaseModel):
    date: str
    quantity: int


class MarketContractResponse(BaseModel):
    """Details of a market contract"""

    expectation_id: int
    title: str
    fitting_id: int
    structure_id: int | None = None
    location_name: str
    desired_quantity: int
    current_quantity: int
    latest_contract_timestamp: str | None = None
    historical_quantity: List[MarketContractHistoricalQuantityResponse]
    responsibilities: List[MarketContractResponsibilityResponse]


class MarketLocationSummary(BaseModel):
    id: int
    name: str
    system_name: str = ""
    contracts: int = 0
    expectations: int = 0
    structure_id: Optional[int] = None


class MarketContractErrorResponse(BaseModel):
    location_name: str
    issuer_id: int
    issuer_name: str
    title: str
    quantity: int


def _get_entity_ids(request):
    characters = (
        EveCharacter.objects.annotate(
            matching_scopes=Count(
                "token__scopes",
                filter=Q(token__scopes__name__in=MARKET_SCOPES),
            )
        )
        .filter(
            matching_scopes=len(MARKET_SCOPES),
            token__user=request.user,
        )
        .distinct()
    )
    corporations = (
        EveCorporation.objects.annotate(
            matching_scopes=Count(
                "ceo__token__scopes",
                filter=Q(ceo__token__scopes__name__in=MARKET_SCOPES),
            )
        )
        .filter(
            matching_scopes=len(MARKET_SCOPES),
            ceo__token__user=request.user,
            alliance__in=EveAlliance.objects.all(),
        )
        .distinct()
    )
    return [character.character_id for character in characters] + [
        corporation.corporation_id for corporation in corporations
    ]


@router.get(
    "/characters",
    auth=AuthBearer(),
    response=List[MarketCharacterResponse],
    description="List all owned characters with sufficient market scopes",
)
def get_market_characters(request):
    characters = (
        EveCharacter.objects.annotate(
            matching_scopes=Count(
                "token__scopes",
                filter=Q(token__scopes__name__in=MARKET_SCOPES),
            )
        )
        .filter(
            matching_scopes=len(MARKET_SCOPES),
            token__user=request.user,
        )
        .distinct()
    )
    response = []
    for character in characters:
        response.append(
            MarketCharacterResponse(
                character_id=character.character_id,
                character_name=character.character_name,
            )
        )

    return response


@router.get(
    "/corporations",
    auth=AuthBearer(),
    response=List[MarketCorporationResponse],
    description="List all owned corporations with sufficient market scopes",
)
def get_market_corporations(request):
    corporations = (
        EveCorporation.objects.annotate(
            matching_scopes=Count(
                "ceo__token__scopes",
                filter=Q(ceo__token__scopes__name__in=MARKET_SCOPES),
            )
        )
        .filter(
            matching_scopes=len(MARKET_SCOPES),
            ceo__token__user=request.user,
            alliance__in=EveAlliance.objects.all(),
        )
        .distinct()
    )
    response = []
    for corporation in corporations:
        response.append(
            MarketCorporationResponse(
                corporation_id=corporation.corporation_id,
                corporation_name=corporation.name,
            )
        )

    return response


@router.get(
    "/expectations",
    auth=AuthBearer(),
    description="Fetch all contract seeding expectations",
    response=List[MarketExpectationResponse],
)
def fetch_eve_market_expectations(request):
    expectations = EveMarketContractExpectation.objects.all()
    response = []
    for expectation in expectations:
        response.append(
            MarketExpectationResponse(
                expectation_id=expectation.id,
                fitting_id=expectation.fitting.id,
                fitting_name=expectation.fitting.name,
                location_id=expectation.location.location_id,
                location_name=expectation.location.location_name,
                quantity=expectation.quantity,
            )
        )

    return response


@router.post(
    "/responsibilities",
    auth=AuthBearer(),
    description="Create a new responsibility for a contract seeding expectation",
    response={
        200: CreateEveMarketContractReponsibilityResponse,
        403: ErrorResponse,
    },
)
def create_eve_market_contract_responsibility(
    request, payload: CreateEveMarketContractReponsibilityRequest
):
    if not request.user.has_perm("market.add_evemarketcontractresponsibility"):
        return 403, {
            "detail": "User missing permission market.add_evemarketcontractresponsibility"
        }
    if payload.entity_id not in _get_entity_ids(request):
        return 403, {"detail": "User does not own entity"}

    expectation = EveMarketContractExpectation.objects.get(
        id=payload.expectation_id
    )
    responsibility = EveMarketContractResponsibility.objects.create(
        expectation=expectation, entity_id=payload.entity_id
    )
    return CreateEveMarketContractReponsibilityResponse(
        responsibility_id=responsibility.id, entity_id=responsibility.entity_id
    )


@router.delete(
    "/responsibilities/{responsibility_id}",
    auth=AuthBearer(),
    description="Delete a responsibility for a contract seeding expectation",
    response={
        204: None,
        403: ErrorResponse,
    },
)
def delete_eve_market_contract_responsibility(request, responsibility_id: int):
    if not EveMarketContractResponsibility.objects.filter(
        id=responsibility_id
    ).exists():
        return 404, {"detail": "Responsibility not found"}

    responsibility = EveMarketContractResponsibility.objects.get(
        id=responsibility_id
    )
    if responsibility.entity_id not in _get_entity_ids(request):
        return 403, {"detail": "User does not own entity"}
    responsibility.delete()
    return 204, None


def _entity_name_by_id(entity_ids):
    """Resolve entity_id to (entity_type, entity_name). Returns dict entity_id -> (type, name)."""
    if not entity_ids:
        return {}
    character_names = dict(
        EveCharacter.objects.filter(character_id__in=entity_ids).values_list(
            "character_id", "character_name"
        )
    )
    corporation_names = dict(
        EveCorporation.objects.filter(
            corporation_id__in=entity_ids
        ).values_list("corporation_id", "name")
    )
    result = {}
    for eid in entity_ids:
        if eid in character_names:
            result[eid] = ("character", character_names[eid])
        elif eid in corporation_names:
            result[eid] = ("corporation", corporation_names[eid])
    return result


@router.get(
    "/contracts",
    description="Fetch all market contracts for all characters and corporations",
    response=List[MarketContractResponse],
)
def fetch_eve_market_contracts(request):
    """
    - Fetch all expectations with related fitting/location
    - Fetch all responsibilities and resolve entity names in bulk
    - Fetch outstanding contract counts and latest timestamp per fitting in one query
    - Populate response
    """
    expectations = EveMarketContractExpectation.objects.select_related(
        "fitting", "location"
    ).all()

    all_responsibilities = list(
        EveMarketContractResponsibility.objects.filter(
            expectation__in=expectations
        )
    )
    entity_ids = {r.entity_id for r in all_responsibilities}
    entity_info = _entity_name_by_id(entity_ids)
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
        historical_quantity: List[MarketContractHistoricalQuantity] = (
            get_historical_quantity(expectation)
        )
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


@router.get(
    "/contracts/{expectation_id}",
    description="Fetch a single market contract by ID",
    response={200: MarketContractResponse, 404: ErrorResponse},
)
def fetch_eve_market_contract(request, expectation_id: int):
    """
    - Fetch expectation with related fitting/location
    - Fetch responsibilities and resolve entity names in bulk
    - Populate data
    """
    expectation = (
        EveMarketContractExpectation.objects.filter(id=expectation_id)
        .select_related("fitting", "location")
        .first()
    )
    if expectation is None:
        return 404, {"detail": "Contract expectation not found"}
    responsibilities_list = list(
        EveMarketContractResponsibility.objects.filter(expectation=expectation)
    )
    entity_ids = [r.entity_id for r in responsibilities_list]
    entity_info = _entity_name_by_id(entity_ids)
    responsibilities = [
        MarketContractResponsibilityResponse(
            entity_type=entity_info[r.entity_id][0],
            entity_id=r.entity_id,
            entity_name=entity_info[r.entity_id][1],
        )
        for r in responsibilities_list
        if r.entity_id in entity_info
    ]
    historical_quantity = get_historical_quantity(expectation)
    outstanding = EveMarketContract.objects.filter(
        fitting=expectation.fitting, status="outstanding"
    )
    current_quantity = outstanding.count()
    latest_agg = outstanding.aggregate(Max("created_at"))
    latest = latest_agg.get("created_at__max")
    return MarketContractResponse(
        expectation_id=expectation.id,
        title=expectation.fitting.name,
        fitting_id=expectation.fitting.id,
        structure_id=None,
        location_name=expectation.location.location_name,
        desired_quantity=expectation.quantity,
        current_quantity=current_quantity,
        latest_contract_timestamp=str(latest) if latest else None,
        historical_quantity=[
            MarketContractHistoricalQuantityResponse(
                date=entry.date, quantity=entry.quantity
            )
            for entry in historical_quantity
        ],
        responsibilities=responsibilities,
    )


@router.get(
    "/expectations/by-location",
    description="Get all market contract expectations grouped by location and fitting",
    response=List[LocationExpectationsResponse],
)
def get_expectations_by_location(
    request,
) -> List[LocationExpectationsResponse]:
    """
    Returns all market contract expectations grouped by location.
    Each location contains a list of fitting expectations.
    """
    # Get all expectations with their locations
    expectations = EveMarketContractExpectation.objects.select_related(
        "location", "fitting"
    ).order_by("location__location_name", "fitting__name")

    # Group by location
    location_map = {}
    for expectation in expectations:
        location_id = expectation.location.location_id
        if location_id not in location_map:
            location_map[location_id] = {
                "location": expectation.location,
                "expectations": [],
            }
        location_map[location_id]["expectations"].append(expectation)

    response = []
    for location_id, data in location_map.items():
        location = data["location"]
        expectations_list = data["expectations"]

        fitting_expectations = []
        for expectation in expectations_list:
            fitting_expectations.append(
                LocationFittingExpectationResponse(
                    fitting_id=expectation.fitting.id,
                    fitting_name=expectation.fitting.name,
                    expectation_id=expectation.id,
                    quantity=expectation.quantity,
                )
            )

        response.append(
            LocationExpectationsResponse(
                location_id=location.location_id,
                location_name=location.location_name,
                solar_system_name=location.solar_system_name,
                short_name=location.short_name,
                expectations=fitting_expectations,
            )
        )

    return response


@router.get(
    "/errors",
    description="Fetch details of errors matching public contracts",
    auth=AuthBearer(),
    response={200: List[MarketContractErrorResponse]},
)
def get_public_contract_errors(request) -> List[MarketContractErrorResponse]:
    results = []
    for contract_error in EveMarketContractError.objects.all():
        results.append(
            MarketContractErrorResponse(
                location_name=contract_error.location.location_name,
                issuer_id=contract_error.issuer.character_id,
                issuer_name=contract_error.issuer.character_name,
                title=contract_error.title,
                quantity=contract_error.quantity,
            )
        )
    return results
