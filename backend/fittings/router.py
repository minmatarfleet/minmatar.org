from datetime import datetime
from typing import List

from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse

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


class DoctrineCompositionItemResponse(BaseModel):
    fitting: FittingResponse
    ideal_ship_count: int


class DoctrineCompositionResponse(BaseModel):
    ideal_fleet_size: int
    composition: List[DoctrineCompositionItemResponse]


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
    )
    return doctrine_response


@doctrines_router.get(
    "/{doctrine_id}/composition",
    response={
        200: DoctrineCompositionResponse,
        404: ErrorResponse,
    },
)
def get_doctrine_composition(request, doctrine_id: int):
    try:
        doctrine = EveDoctrine.objects.get(id=doctrine_id)
        fittings = EveDoctrineFitting.objects.filter(doctrine=doctrine)
    except EveDoctrine.DoesNotExist:
        return 404, ErrorResponse(
            status=404,
            message="Doctrine details not found",
        )

    doctrine_items = []
    for doctrine_fitting in fittings:
        fitting = doctrine_fitting.fitting
        composition_item = DoctrineCompositionItemResponse(
            fitting=make_fitting_response(fitting),
            ideal_ship_count=doctrine_fitting.ideal_ship_count,
        )
        doctrine_items.append(composition_item)

    return DoctrineCompositionResponse(
        ideal_fleet_size=doctrine.ideal_fleet_size,
        composition=doctrine_items,
    )


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
