import logging
from typing import List, Optional

from django.db.models import Count, Q, Max
from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveCharacter, EveCorporation, EveLocation
from eveonline.scopes import MARKET_ADDITIONAL_SCOPES
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
                filter=Q(token__scopes__name__in=MARKET_ADDITIONAL_SCOPES),
            )
        )
        .filter(
            matching_scopes=len(MARKET_ADDITIONAL_SCOPES),
            token__user=request.user,
        )
        .distinct()
    )
    corporations = (
        EveCorporation.objects.annotate(
            matching_scopes=Count(
                "ceo__token__scopes",
                filter=Q(
                    ceo__token__scopes__name__in=MARKET_ADDITIONAL_SCOPES
                ),
            )
        )
        .filter(
            matching_scopes=len(MARKET_ADDITIONAL_SCOPES),
            ceo__token__user=request.user,
            alliance__name__in=[
                "Minmatar Fleet Alliance",
                "Minmatar Fleet Associates",
            ],
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
                filter=Q(token__scopes__name__in=MARKET_ADDITIONAL_SCOPES),
            )
        )
        .filter(
            matching_scopes=len(MARKET_ADDITIONAL_SCOPES),
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
                filter=Q(
                    ceo__token__scopes__name__in=MARKET_ADDITIONAL_SCOPES
                ),
            )
        )
        .filter(
            matching_scopes=len(MARKET_ADDITIONAL_SCOPES),
            ceo__token__user=request.user,
            alliance__name__in=[
                "Minmatar Fleet Alliance",
                "Minmatar Fleet Associates",
            ],
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


@router.get(
    "/contracts",
    description="Fetch all market contracts for all characters and corporations",
    response=List[MarketContractResponse],
)
def fetch_eve_market_contracts(request):
    """
    - Fetch all expectations
    - Fetch current quantity for all expectations
    - Fetch all responsibilities
    - Populate data
    """
    expectations = EveMarketContractExpectation.objects.all()
    response = []
    for expectation in expectations:
        responsibilities = []
        for responsibility in EveMarketContractResponsibility.objects.filter(
            expectation=expectation
        ):
            entity_type = None
            entity_name = None
            if EveCharacter.objects.filter(
                character_id=responsibility.entity_id
            ).exists():
                entity_type = "character"
                entity_name = EveCharacter.objects.get(
                    character_id=responsibility.entity_id
                ).character_name
            elif EveCorporation.objects.filter(
                corporation_id=responsibility.entity_id
            ).exists():
                entity_type = "corporation"
                entity_name = EveCorporation.objects.get(
                    corporation_id=responsibility.entity_id
                ).name
            else:
                continue
            assert entity_type is not None
            assert entity_name is not None
            responsibilities.append(
                MarketContractResponsibilityResponse(
                    entity_type=entity_type,
                    entity_id=responsibility.entity_id,
                    entity_name=entity_name,
                )
            )
        historical_quantity: List[MarketContractHistoricalQuantity] = (
            get_historical_quantity(expectation)
        )

        try:
            latest = EveMarketContract.objects.filter(
                fitting=expectation.fitting, status="outstanding"
            ).aggregate(Max("created_at", default=None))["created_at__max"]
        except Exception as e:
            logger.error("Error fetching last timestamp, %s", e)
            latest = None

        response.append(
            MarketContractResponse(
                expectation_id=expectation.id,
                title=expectation.fitting.name,
                fitting_id=expectation.fitting.id,
                structure_id=(
                    expectation.location.structure.id
                    if expectation.location.structure
                    else None
                ),
                location_name=expectation.location.location_name,
                desired_quantity=expectation.quantity,
                current_quantity=EveMarketContract.objects.filter(
                    fitting=expectation.fitting, status="outstanding"
                ).count(),
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
    - Fetch all expectations
    - Fetch current quantity for all expectations
    - Fetch all responsibilities
    - Populate data
    """
    if not EveMarketContractExpectation.objects.filter(
        id=expectation_id
    ).exists():
        return 404, {"detail": "Contract expectation not found"}
    expectation = EveMarketContractExpectation.objects.get(id=expectation_id)
    responsibilities = []
    for responsibility in EveMarketContractResponsibility.objects.filter(
        expectation=expectation
    ):
        entity_type = None
        entity_name = None
        if EveCharacter.objects.filter(
            character_id=responsibility.entity_id
        ).exists():
            entity_type = "character"
            entity_name = EveCharacter.objects.get(
                character_id=responsibility.entity_id
            ).character_name
        elif EveCorporation.objects.filter(
            corporation_id=responsibility.entity_id
        ).exists():
            entity_type = "corporation"
            entity_name = EveCorporation.objects.get(
                corporation_id=responsibility.entity_id
            ).name
        else:
            continue
        assert entity_type is not None
        assert entity_name is not None
        responsibilities.append(
            MarketContractResponsibilityResponse(
                entity_type=entity_type,
                entity_id=responsibility.entity_id,
                entity_name=entity_name,
            )
        )
    historical_quantity = get_historical_quantity(expectation)
    return MarketContractResponse(
        expectation_id=expectation.id,
        title=expectation.fitting.name,
        fitting_id=expectation.fitting.id,
        structure_id=(
            expectation.location.structure.id
            if expectation.location.structure
            else None
        ),
        location_name=expectation.location.location_name,
        desired_quantity=expectation.quantity,
        current_quantity=EveMarketContract.objects.filter(
            fitting=expectation.fitting, status="outstanding"
        ).count(),
        historical_quantity=[
            MarketContractHistoricalQuantityResponse(
                date=entry.date, quantity=entry.quantity
            )
            for entry in historical_quantity
        ],
        responsibilities=responsibilities,
    )


@router.get(
    "/locations",
    description="Fetch summaries of all market locations",
    response={200: List[MarketLocationSummary]},
)
def get_market_locations(request) -> List[MarketLocationSummary]:
    locations = []
    for location in EveLocation.objects.filter(market_active=True):
        contract_count = EveMarketContract.objects.filter(
            location=location,
            status="outstanding",
        ).count()
        expectation_count = EveMarketContractExpectation.objects.filter(
            location=location
        ).count()
        locations.append(
            MarketLocationSummary(
                id=location.location_id,
                name=location.location_name,
                system_name=location.solar_system_name,
                structure_id=location.structure_id,
                contracts=contract_count,
                expectations=expectation_count,
            )
        )
    return locations


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
