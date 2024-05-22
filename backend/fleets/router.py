from datetime import datetime
from enum import Enum
from typing import List, Optional

from django.contrib.auth.models import Group
from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from fittings.models import EveDoctrine
from structures.models import EveStructure

from .models import (
    EveFleet,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetNotificationChannel,
)

router = Router(tags=["Fleets"])


class EveFleetType(str, Enum):
    STRATOP = "stratop"
    NON_STRATEGIC = "non_strategic"
    CASUAL = "casual"
    TRAINING = "training"


class EveFleetChannelResponse(BaseModel):
    id: int
    display_name: str
    display_channel_name: str


class EveFleetTrackingResponse(BaseModel):
    id: int
    is_registered: bool

    class Config:
        from_attributes = True


class EveFleetResponse(BaseModel):
    id: int
    type: EveFleetType
    description: str
    start_time: datetime
    fleet_commander: int
    doctrine_id: Optional[int] = None
    location: str

    tracking: Optional[EveFleetTrackingResponse] = None


class EveFleetMemberResponse(BaseModel):
    character_id: int
    character_name: str
    ship_type_id: int
    ship_type_name: str
    solar_system_id: int
    solar_system_name: str


class EveFleetLocationResponse(BaseModel):
    location_id: int
    location_name: str


class CreateEveFleetRequest(BaseModel):
    type: EveFleetType
    description: str
    start_time: datetime
    doctrine_id: Optional[int] = None
    audience_id: int
    location: str


@router.get(
    "/types",
    auth=AuthBearer(),
    response={200: List[EveFleetType], 403: ErrorResponse},
)
def get_fleet_types(request):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}
    return [
        EveFleetType.STRATOP,
        EveFleetType.NON_STRATEGIC,
        EveFleetType.CASUAL,
        EveFleetType.TRAINING,
    ]


@router.get(
    "/locations",
    auth=AuthBearer(),
    response={200: List[str], 403: ErrorResponse},
)
def get_fleet_locations(request):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}
    return list(
        EveStructure.objects.filter(is_valid_staging=True).values_list(
            "name", flat=True
        )
    )


@router.get(
    "/v2/locations",
    auth=AuthBearer(),
    response={200: List[EveFleetLocationResponse], 403: ErrorResponse},
)
def get_v2_fleet_locations(request):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}
    response = []
    locations = EveStructure.objects.filter(is_valid_staging=True).values_list(
        "name", flat=True
    )
    for location in locations:
        response.append(
            {"location_id": location.id, "location_name": location.name}
        )
    return response


@router.get(
    "/audiences",
    auth=AuthBearer(),
    response={200: List[EveFleetChannelResponse], 403: ErrorResponse},
)
def get_fleet_audiences(request):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}
    available_channels = EveFleetNotificationChannel.objects.filter(
        group__in=request.user.groups.all()
    )
    response = []
    for channel in available_channels:
        response.append(
            {
                "id": channel.group.id,
                "display_name": channel.group.name,
                "display_channel_name": channel.discord_channel_name,
            }
        )
    return response


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
    response={200: EveFleetResponse, 403: None, 404: None},
    description="Get fleet by ID, must be the owner, in the audience, or have fleets.view_evefleet permission",
)
def get_fleet(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    is_authorized = False
    if request.user.has_perm("fleets.view_evefleet"):
        is_authorized = True
    if request.user == fleet.created_by:
        is_authorized = True
    if fleet.audience in request.user.groups.all():
        is_authorized = True

    if not is_authorized:
        return 403, None

    tracking = None
    if EveFleetInstance.objects.filter(eve_fleet=fleet).exists():
        tracking = EveFleetTrackingResponse.model_validate(
            EveFleetInstance.objects.get(eve_fleet=fleet)
        )

    payload = {
        "id": fleet.id,
        "type": fleet.type,
        "description": fleet.description,
        "start_time": fleet.start_time,
        "fleet_commander": fleet.created_by.id,
        "location": fleet.location,
        "tracking": tracking,
    }
    if fleet.doctrine:
        payload["doctrine_id"] = fleet.doctrine.id

    return EveFleetResponse(**payload)


@router.get(
    "/{fleet_id}/members",
    auth=AuthBearer(),
    response={200: List[EveFleetMemberResponse], 403: None, 404: None},
    description="Get fleet members, must be the owner, in the audience, or have fleets.view_evefleet permission",
)
def get_fleet_members(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    is_authorized = False
    if request.user.has_perm("fleets.view_evefleet"):
        is_authorized = True
    if request.user == fleet.created_by:
        is_authorized = True
    if fleet.audience in request.user.groups.all():
        is_authorized = True

    if not is_authorized:
        return 403, None

    response = []
    for member in EveFleetInstanceMember.objects.filter(
        eve_fleet_instance__eve_fleet=fleet
    ):
        response.append(
            {
                "character_id": member.character_id,
                "character_name": member.character_name,
                "ship_type_id": member.ship_type_id,
                "ship_type_name": member.ship_name,
                "solar_system_id": member.solar_system_id,
                "solar_system_name": member.solar_system_name,
            }
        )

    return response


@router.post(
    "",
    auth=AuthBearer(),
    response={200: EveFleetResponse, 403: ErrorResponse, 400: ErrorResponse},
    description="Create a new fleet, type/location/audience is from other endpoints. Must have fleets.add_evefleet permission",
)
def create_fleet(request, payload: CreateEveFleetRequest):
    if not request.user.has_perm("fleets.add_evefleet"):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}

    if not Group.objects.filter(id=payload.audience_id).exists():
        return 400, {"detail": "Group does not exist for audience"}

    if not EveFleetNotificationChannel.objects.filter(
        group_id=payload.audience_id
    ).exists():
        return 400, {"detail": "Group does not have a notification channel"}

    audience = Group.objects.get(id=payload.audience_id)

    fleet = EveFleet.objects.create(
        type=payload.type,
        description=payload.description,
        start_time=payload.start_time,
        created_by=request.user,
        location=payload.location,
        audience=audience,
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


@router.post(
    "/{fleet_id}/tracking",
    auth=AuthBearer(),
    response={200: None, 403: ErrorResponse},
    description="Start a fleet and send a discord ping, must be the owner of the fleet",
)
def start_fleet(request, fleet_id: int):
    fleet = EveFleet.objects.get(id=fleet_id)
    if request.user != fleet.created_by:
        return 403, {
            "detail": "User does not have permission to start tracking this fleet"
        }
    try:
        fleet.start()
    except Exception as e:
        return 400, {"detail": str(e)}

    return 200, None


@router.delete(
    "/{fleet_id}",
    auth=AuthBearer(),
    response={200: None, 403: ErrorResponse},
    description="Delete a fleet, must be owner or have fleets.delete_evefleet permission",
)
def delete_fleet(request, fleet_id: int):
    fleet = EveFleet.objects.get(id=fleet_id)
    if request.user != fleet.created_by and not request.user.has_perm(
        "fleets.delete_evefleet"
    ):
        return 403, {
            "detail": "User does not have permission to delete this fleet"
        }
    fleet.delete()
    return 200, None
