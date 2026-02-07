from datetime import datetime
from typing import List

from django.db.models import OuterRef, Subquery
from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from eveonline.models import EveLocation
from eveuniverse.models import EveType

from .models import (
    EveDoctrine,
    EveDoctrineFitting,
    EveFitting,
    EveFittingRefit,
)

doctrines_router = Router(tags=["Ships"])
fittings_router = Router(tags=["Ships"])


class RefitResponse(BaseModel):
    """Refit API Response"""

    id: int
    name: str
    eft_format: str
    description: str
    created_at: datetime
    updated_at: datetime


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
    refits: List[RefitResponse]


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
    doctrines = EveDoctrine.objects.prefetch_related(
        "evedoctrinefitting_set__fitting__tags",
        "evedoctrinefitting_set__fitting__refits",
    )
    response = []
    for doctrine in doctrines:
        primary_fittings = []
        secondary_fittings = []
        support_fittings = []
        for doctrine_fitting in doctrine.evedoctrinefitting_set.all():
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
    fittings = (
        EveDoctrineFitting.objects.filter(doctrine=doctrine)
        .select_related("fitting")
        .prefetch_related("fitting__tags", "fitting__refits")
    )
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


def make_refit_response(refit: EveFittingRefit) -> RefitResponse:
    return RefitResponse(
        id=refit.id,
        name=refit.name,
        eft_format=refit.eft_format,
        description=refit.description or "",
        created_at=refit.created_at,
        updated_at=refit.updated_at,
    )


def make_fitting_response(fitting: EveFitting) -> FittingResponse:
    refits = [make_refit_response(refit) for refit in fitting.refits.all()]
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
        refits=refits,
    )


@fittings_router.get("", response=List[FittingResponse])
def get_fittings(request):
    fittings = EveFitting.objects.prefetch_related("tags", "refits")
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
    fitting = EveFitting.objects.prefetch_related("tags", "refits").get(
        id=fitting_id
    )
    fitting_response = make_fitting_response(fitting)
    return fitting_response


class DoctrineFittingResponse(BaseModel):
    """Fitting in a doctrine"""

    fitting_id: int
    fitting_name: str
    role: str


@doctrines_router.get(
    "/market/locations",
    description="Get all fittings from doctrines assigned to market-active locations",
    response=List[DoctrineFittingResponse],
)
def get_market_locations_with_doctrines(
    request,
) -> List[DoctrineFittingResponse]:
    """
    Returns all fittings that belong to doctrines assigned to market-active locations.
    Fittings are sorted by ship volume (desc) then name. Excludes secondary fittings.
    """
    # Get all market-active locations
    active_locations = EveLocation.objects.filter(market_active=True)

    # Get all fittings that belong to doctrines assigned to market-active locations
    # Exclude secondary fittings
    # Join with EveType to sort by ship volume (size), then by name
    ship_volume_subquery = EveType.objects.filter(
        id=OuterRef("fitting__ship_id")
    ).values("packaged_volume")[:1]

    doctrine_fittings = (
        EveDoctrineFitting.objects.filter(
            doctrine__locations__in=active_locations
        )
        .exclude(role="secondary")
        .select_related("fitting")
        .annotate(ship_volume=Subquery(ship_volume_subquery))
        .distinct()
        .order_by("-ship_volume", "fitting__name")
    )

    response = []
    seen_fitting_ids = set()

    for doctrine_fitting in doctrine_fittings:
        fitting = doctrine_fitting.fitting

        # Skip duplicates
        if fitting.id in seen_fitting_ids:
            continue

        seen_fitting_ids.add(fitting.id)

        response.append(
            DoctrineFittingResponse(
                fitting_id=fitting.id,
                fitting_name=fitting.name,
                role=doctrine_fitting.role,
            )
        )

    return response
