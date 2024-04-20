from datetime import datetime
from enum import Enum
from typing import List, Optional

from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer
from fittings.models import EveDoctrine
from structures.models import EveStructure

from .models import EveFleet

router = Router(tags=["Fleets"])


class EveFleetType(str, Enum):
    STRATOP = "stratop"
    NON_STRATEGIC = "non_strategic"
    CASUAL = "casual"
    TRAINING = "training"


class EveFleetResponse(BaseModel):
    id: int
    type: EveFleetType
    description: str
    start_time: datetime
    fleet_commander: int
    doctrine_id: Optional[int] = None
    location: str


class CreateEveFleetRequest(BaseModel):
    type: EveFleetType
    description: str
    start_time: datetime
    doctrine_id: Optional[int] = None
    location: str


@router.get(
    "/types", auth=AuthBearer(), response={200: List[EveFleetType], 403: None}
)
def get_fleet_types(request):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, None
    return [
        EveFleetType.STRATOP,
        EveFleetType.NON_STRATEGIC,
        EveFleetType.CASUAL,
        EveFleetType.TRAINING,
    ]


@router.get(
    "/locations", auth=AuthBearer(), response={200: List[str], 403: None}
)
def get_fleet_locations(request):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, None
    return list(
        EveStructure.objects.filter(is_valid_staging=True).values_list(
            "name", flat=True
        )
    )


@router.get("", response={200: List[int]})
def get_fleets(request, upcoming: bool = True):
    if upcoming:
        fleets = EveFleet.objects.filter(start_time__gte=datetime.now())
    else:
        fleets = EveFleet.objects.all()
    return [fleet.id for fleet in fleets]


@router.get(
    "/{fleet_id}",
    auth=AuthBearer(),
    response={200: EveFleetResponse, 403: None},
)
def get_fleet(request, fleet_id: int):
    fleet = EveFleet.objects.get(id=fleet_id)
    is_authorized = False
    if request.user.has_perm("fleets.view_evefleet"):
        is_authorized = True
    if request.user == fleet.created_by:
        is_authorized = True
    for group in fleet.audience.all():
        if group in request.user.groups.all():
            is_authorized = True

    if not is_authorized:
        return 403, None

    payload = {
        "id": fleet.id,
        "type": fleet.type,
        "description": fleet.description,
        "start_time": fleet.start_time,
        "fleet_commander": fleet.created_by.id,
        "location": fleet.location,
    }
    if fleet.doctrine:
        payload["doctrine_id"] = fleet.doctrine.id

    return EveFleetResponse(**payload)


@router.post(
    "", auth=AuthBearer(), response={200: EveFleetResponse, 403: None}
)
def create_fleet(request, payload: CreateEveFleetRequest):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, None
    fleet = EveFleet.objects.create(
        type=payload.type,
        description=payload.description,
        start_time=payload.start_time,
        created_by=request.user,
        location=payload.location,
    )
    if payload.doctrine_id:
        doctrine = EveDoctrine.objects.get(id=payload.doctrine_id)
        fleet.doctrine = doctrine
        fleet.save()
    payload = {
        "id": fleet.id,
        "type": fleet.type,
        "description": fleet.description,
        "start_time": fleet.start_time,
        "fleet_commander": fleet.created_by.id,
        "location": fleet.location,
    }
    if fleet.doctrine:
        payload["doctrine_id"] = fleet.doctrine.id

    return EveFleetResponse(**payload)


@router.delete("/{fleet_id}", auth=AuthBearer(), response={200: None})
def delete_fleet(request, fleet_id: int):
    fleet = EveFleet.objects.get(id=fleet_id)
    if request.user != fleet.created_by and not request.user.has_perm(
        "fleets.delete_evefleet"
    ):
        return 403, None
    fleet.delete()
    return 200, None
