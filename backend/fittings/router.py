from datetime import datetime
from typing import List

from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from eveonline.models import EveLocation
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
)

from .models import EveDoctrine, EveDoctrineFitting, EveFitting

doctrines_router = Router(tags=["Ships"])
fittings_router = Router(tags=["Ships"])


class FittingResponse(BaseModel):
    """Fittings API Response"""

    id: int
    name: str
    ship_id: int
    description: str
    created_at: datetime
    updated_at: datetime
    tags: List[str]
    eft_format: str
    minimum_pod: str
    recommended_pod: str

    latest_version: str


class DoctrineResponse(BaseModel):
    """Doctrines API Response"""

    id: int
    name: str
    type: str
    created_at: datetime
    updated_at: datetime
    description: str
    primary_fittings: List[FittingResponse]
    secondary_fittings: List[FittingResponse]
    support_fittings: List[FittingResponse]
    sig_ids: List[int]
    location_ids: List[int]


@doctrines_router.get("", response=List[DoctrineResponse])
def get_doctrines(request):
    doctrines = EveDoctrine.objects.all()
    response = []
    for doctrine in doctrines:
        primary_fittings = []
        secondary_fittings = []
        support_fittings = []
        fittings = EveDoctrineFitting.objects.filter(doctrine=doctrine)
        for doctrine_fitting in fittings:
            fitting = doctrine_fitting.fitting
            fitting_response = make_fitting_response(fitting)
            if doctrine_fitting.role == "primary":
                primary_fittings.append(fitting_response)
            elif doctrine_fitting.role == "secondary":
                secondary_fittings.append(fitting_response)
            elif doctrine_fitting.role == "support":
                support_fittings.append(fitting_response)
        doctrine_response = DoctrineResponse(
            id=doctrine.id,
            name=doctrine.name,
            type=doctrine.type,
            created_at=doctrine.created_at,
            updated_at=doctrine.updated_at,
            description=doctrine.description,
            primary_fittings=primary_fittings,
            secondary_fittings=secondary_fittings,
            support_fittings=support_fittings,
            sig_ids=[sig.id for sig in doctrine.sigs.all()],
            location_ids=[
                location.location_id for location in doctrine.locations.all()
            ],
        )
        response.append(doctrine_response)
    return response


@doctrines_router.get(
    "/{doctrine_id}", response={200: DoctrineResponse, 404: ErrorResponse}
)
def get_doctrine(request, doctrine_id: int):
    if not EveDoctrine.objects.filter(id=doctrine_id).exists():
        return 404, ErrorResponse(
            status=404,
            detail="Doctrine not found",
        )

    doctrine = EveDoctrine.objects.get(id=doctrine_id)
    primary_fittings = []
    secondary_fittings = []
    support_fittings = []
    fittings = EveDoctrineFitting.objects.filter(doctrine=doctrine)
    for doctrine_fitting in fittings:
        fitting = doctrine_fitting.fitting
        fitting_response = make_fitting_response(fitting)
        if doctrine_fitting.role == "primary":
            primary_fittings.append(fitting_response)
        elif doctrine_fitting.role == "secondary":
            secondary_fittings.append(fitting_response)
        elif doctrine_fitting.role == "support":
            support_fittings.append(fitting_response)
    doctrine_response = DoctrineResponse(
        id=doctrine.id,
        name=doctrine.name,
        type=doctrine.type,
        created_at=doctrine.created_at,
        updated_at=doctrine.updated_at,
        description=doctrine.description,
        primary_fittings=primary_fittings,
        secondary_fittings=secondary_fittings,
        support_fittings=support_fittings,
        sig_ids=[sig.id for sig in doctrine.sigs.all()],
        location_ids=[
            location.location_id for location in doctrine.locations.all()
        ],
    )
    return doctrine_response


def make_fitting_response(fitting: EveFitting) -> FittingResponse:
    return FittingResponse(
        id=fitting.id,
        name=fitting.name,
        ship_id=fitting.ship_id,
        description=fitting.description,
        created_at=fitting.created_at,
        updated_at=fitting.updated_at,
        tags=[tag.name for tag in fitting.tags.all()],
        eft_format=fitting.eft_format,
        minimum_pod=fitting.minimum_pod,
        recommended_pod=fitting.recommended_pod,
        latest_version=fitting.latest_version,
    )


@fittings_router.get("", response=List[FittingResponse])
def get_fittings(request):
    fittings = EveFitting.objects.all()
    response = []
    for fitting in fittings:
        fitting_response = make_fitting_response(fitting)
        response.append(fitting_response)
    return response


@fittings_router.get(
    "/{fitting_id}", response={200: FittingResponse, 404: ErrorResponse}
)
def get_fitting(request, fitting_id: int):
    if not EveFitting.objects.filter(id=fitting_id).exists():
        return 404, ErrorResponse(
            status=404,
            detail=f"Fitting not found: {fitting_id}",
        )
    fitting = EveFitting.objects.get(id=fitting_id)
    fitting_response = make_fitting_response(fitting)
    return fitting_response


class DoctrineFittingResponse(BaseModel):
    """Fitting in a doctrine with market information"""

    fitting_id: int
    fitting_name: str
    role: str
    quantity: int  # expectation quantity if exists, otherwise current quantity
    has_expectation: bool


class DoctrineMarketResponse(BaseModel):
    """Doctrine with its fittings and market data"""

    doctrine_id: int
    doctrine_name: str
    fittings: List[DoctrineFittingResponse]


class MarketLocationDoctrineResponse(BaseModel):
    """Location with its doctrines and fittings"""

    location_id: int
    location_name: str
    solar_system_name: str
    short_name: str
    doctrines: List[DoctrineMarketResponse]


@doctrines_router.get(
    "/market/locations",
    description="Fetch all market-active locations with their doctrines and fittings",
    response=List[MarketLocationDoctrineResponse],
)
def get_market_locations_with_doctrines(
    request,
) -> List[MarketLocationDoctrineResponse]:
    """
    Returns all locations with market_active=True, grouped by doctrine.
    For each fitting in a doctrine, shows expectation quantity if it exists,
    otherwise shows current quantity of outstanding contracts.
    """
    # Get all market-active locations
    active_locations = EveLocation.objects.filter(market_active=True).order_by(
        "location_name"
    )

    response = []

    for location in active_locations:
        # Get all doctrines that use this location
        doctrines = EveDoctrine.objects.filter(locations=location).order_by(
            "name"
        )

        doctrine_responses = []

        for doctrine in doctrines:
            # Get all fittings for this doctrine
            doctrine_fittings = (
                EveDoctrineFitting.objects.filter(doctrine=doctrine)
                .select_related("fitting")
                .order_by("fitting__name")
            )

            fitting_responses = []

            for doctrine_fitting in doctrine_fittings:
                fitting = doctrine_fitting.fitting

                # Check if there's an expectation for this fitting at this location
                expectation = EveMarketContractExpectation.objects.filter(
                    fitting=fitting, location=location
                ).first()

                if expectation:
                    # Use expectation quantity
                    quantity = expectation.quantity
                    has_expectation = True
                else:
                    # Use current quantity of outstanding contracts
                    quantity = EveMarketContract.objects.filter(
                        fitting=fitting,
                        location=location,
                        status="outstanding",
                    ).count()
                    has_expectation = False

                fitting_responses.append(
                    DoctrineFittingResponse(
                        fitting_id=fitting.id,
                        fitting_name=fitting.name,
                        role=doctrine_fitting.role,
                        quantity=quantity,
                        has_expectation=has_expectation,
                    )
                )

            if fitting_responses:  # Only add doctrine if it has fittings
                doctrine_responses.append(
                    DoctrineMarketResponse(
                        doctrine_id=doctrine.id,
                        doctrine_name=doctrine.name,
                        fittings=fitting_responses,
                    )
                )

        if (
            doctrine_responses
        ):  # Only add location if it has doctrines with fittings
            response.append(
                MarketLocationDoctrineResponse(
                    location_id=location.location_id,
                    location_name=location.location_name,
                    solar_system_name=location.solar_system_name,
                    short_name=location.short_name,
                    doctrines=doctrine_responses,
                )
            )

    return response
