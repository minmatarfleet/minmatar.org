import logging
from datetime import datetime
from enum import Enum
from typing import List

from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer

from structures.helpers import (
    get_skyhook_details,
    get_structure_details,
    get_generic_details,
)
from .models import EveStructure, EveStructureTimer

router = Router(tags=["Structures"])
logger = logging.getLogger(__name__)


class EveStructureState(Enum):
    """States for Eve Structures"""

    ANCHORING = "anchoring"
    ARMOR = "armor"
    HULL = "hull"
    UNANCHORING = "unanchoring"


class EveStructureType(Enum):
    """Eve Structure Types"""

    ASTRAHUS = "astrahus"
    FORTIZAR = "fortizar"
    KEEPSTAR = "keepstar"
    RAITARU = "raitaru"
    AZBEL = "azbel"
    SOTIYO = "sotiyo"
    ATHANOR = "athanor"
    TATARA = "tatara"
    TENEBREX_CYNO_JAMMER = "tenebrex_cyno_jammer"
    PHAROLUX_CYNO_BEACON = "pharolux_cyno_beacon"
    ANSIBLEX_JUMP_GATE = "ansiblex_jump_gate"
    ORBITAL_SKYHOOK = "orbital_skyhook"
    METENOX_MOON_DRILL = "metenox_moon_drill"
    PLAYER_OWNED_CUSTOMS_OFFICE = "player_owned_customs_office"
    PLAYER_OWNED_STARBASE = "player_owned_starbase"
    MERCENARY_DEN = "mercenary_den"


class StructureResponse(BaseModel):
    """Response model for structures API"""

    id: int
    name: str
    type: str
    fuel_expires: datetime


class EveStructureTimerRequest(BaseModel):
    """Request model for structure timer API"""

    selected_item_window: str
    corporation_name: str
    state: EveStructureState
    type: EveStructureType

    structure_name: str = None
    location: str = None
    timer: datetime = None


class EveStructureTimerVerificationRequest(BaseModel):
    """Request model for structure timer API"""

    corporation_name: str
    alliance_name: str | None = None


class EveStructureTimerResponse(BaseModel):
    """Response model for structure timer API"""

    id: int
    name: str
    state: str
    type: str
    timer: datetime
    created_at: datetime
    updated_at: datetime | None = None
    created_by: int | None = None
    updated_by: int | None = None
    system_name: str
    corporation_name: str | None = None
    alliance_name: str | None = None
    structure_id: int | None = None


@router.get(
    "", auth=AuthBearer(), response={200: List[StructureResponse], 403: None}
)
def get_structures(request):
    if not request.user.has_perm("structures.view_evestructure"):
        return 403, None
    structures = EveStructure.objects.all()
    response = []
    for structure in structures:
        response.append(
            StructureResponse(
                id=structure.id,
                name=structure.name,
                type=structure.type_name,
                fuel_expires=structure.fuel_expires,
            )
        )
    return response


@router.get(
    "/timers",
    auth=AuthBearer(),
    response={200: List[EveStructureTimerResponse], 403: None},
)
def get_structure_timers(request, active: bool = True):
    if not request.user.has_perm("structures.view_evestructuretimer"):
        return 403, None

    if active:
        # get timers that are not expired
        timers = EveStructureTimer.objects.filter(timer__gte=datetime.now())
    else:
        timers = EveStructureTimer.objects.all()

    response = []
    for timer in timers:
        response_item = {
            "id": timer.id,
            "name": timer.name,
            "state": timer.state,
            "type": timer.type,
            "timer": timer.timer,
            "created_at": timer.created_at,
            "updated_at": timer.updated_at,
            "created_by": timer.created_by.id if timer.created_by else None,
            "system_name": timer.system_name,
            "corporation_name": timer.corporation_name,
            "alliance_name": timer.alliance_name,
            "structure_id": timer.structure.id if timer.structure else None,
        }
        response.append(response_item)

    return response


@router.post(
    "/timers",
    auth=AuthBearer(),
    description="If structure_name is not provided, selected_item_window will be parsed for values.",
    response={
        200: EveStructureTimerResponse,
        403: ErrorResponse,
        400: ErrorResponse,
    },
)
def create_structure_timer(request, payload: EveStructureTimerRequest):
    """
    Users paste something like
    Sosala - WATERMELLON
    0 m
    Reinforced until 2024.06.23 23:20:58

    Which is
    system_name - structure_name
    distance
    state until datetime

    Parse this and create an EveStructureTimer
    """
    if not request.user.has_perm("structures.add_evestructuretimer"):
        return 403, ErrorResponse(message="Permission denied")

    # Parse the request
    try:
        if payload.structure_name:
            structure_response = get_generic_details(
                payload.structure_name,
                payload.location,
                payload.timer,
            )
        elif "Orbital Skyhook" in payload.selected_item_window:
            structure_response = get_skyhook_details(
                payload.selected_item_window
            )
        else:
            structure_response = get_structure_details(
                payload.selected_item_window
            )
    except ValueError as e:
        return 400, ErrorResponse.log("Invalid request", str(e))

    # Create the structure timer
    timer = EveStructureTimer.objects.create(
        state=payload.state.value,
        type=payload.type.value,
        timer=structure_response.timer,
        created_by=request.user,
        corporation_name=payload.corporation_name,
        system_name=structure_response.location,
        name=structure_response.structure_name,
    )

    logger.info("Timer %d submitted by %s", timer.id, request.user.username)

    response = {
        "id": timer.id,
        "state": timer.state,
        "type": timer.type,
        "timer": timer.timer,
        "created_at": timer.created_at,
        "created_by": timer.created_by.id,
        "system_name": timer.system_name,
        "corporation_name": timer.corporation_name,
        "name": timer.name,
    }

    return response


@router.post(
    "/timers/{timer_id}/verify",
    auth=AuthBearer(),
    response={
        200: EveStructureTimerResponse,
        403: ErrorResponse,
        400: ErrorResponse,
    },
)
def verify_structure_timer(
    request, timer_id: int, payload: EveStructureTimerVerificationRequest
):
    if not request.user.has_perm("structures.change_evestructuretimer"):
        return 403, ErrorResponse(message="Permission denied")

    try:
        timer = EveStructureTimer.objects.get(id=timer_id)
    except EveStructureTimer.DoesNotExist:
        return 400, ErrorResponse(detail="Timer does not exist")

    timer.updated_by = request.user
    timer.updated_at = datetime.now()
    timer.corporation_name = payload.corporation_name
    timer.alliance_name = payload.alliance_name
    timer.save()

    response = {
        "id": timer.id,
        "state": timer.state,
        "type": timer.type,
        "timer": timer.timer,
        "created_at": timer.created_at,
        "updated_at": timer.updated_at,
        "created_by": timer.created_by.id,
        "updated_by": timer.updated_by.id,
        "system_name": timer.system_name,
        "name": timer.name,
    }

    return response
