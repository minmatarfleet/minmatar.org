import logging
from datetime import datetime
from enum import Enum
from typing import List

from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import can_use_feature

from structures.helpers import (
    get_skyhook_details,
    get_structure_details,
    get_generic_details,
)
from audit.models import AuditEntry
from .models import EveStructure, EveStructurePing, EveStructureTimer

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
    campaign_id: int | None = None
    fitting: str | None = None


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
    campaign_id: int | None = None
    fitting: str | None = None


@router.get(
    "", auth=AuthBearer(), response={200: List[StructureResponse], 403: None}
)
def get_structures(request):
    if not can_use_feature(request.user, "structures.view"):
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
    if not can_use_feature(request.user, "structures.timers.view"):
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
            "campaign_id": timer.campaign_id,
            "fitting": timer.fitting,
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
    if not can_use_feature(request.user, "structures.timers.manage"):
        return 403, ErrorResponse(detail="Permission denied")

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
        campaign_id=payload.campaign_id,
        fitting=payload.fitting or None,
    )

    if payload.campaign_id:
        _attach_timer_to_campaign(payload.campaign_id, timer, request.user)

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
        "campaign_id": timer.campaign_id,
        "fitting": timer.fitting,
    }

    return response


def _attach_timer_to_campaign(campaign_id: int, timer, user) -> None:
    """Best-effort link so a bad campaign id does not fail timer create.

    Imported lazily: campaigns.endpoints.manage already imports this module's
    helpers, and loading campaigns.models at module import time would cycle.
    """
    # pylint: disable=import-outside-toplevel
    from campaigns.models import Campaign
    from campaigns.services import structures as structure_service

    campaign = Campaign.objects.filter(id=campaign_id).first()
    if campaign:
        structure_service.attach_timer(campaign, timer, created_by=user)


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
    if not can_use_feature(request.user, "structures.timers.manage"):
        return 403, ErrorResponse(detail="Permission denied")

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


CORRECT_FEATURE = "structures.timers.correct"


class EveStructureTimerPatch(BaseModel):
    """Fix a wrong timer: only the fields sent change."""

    name: str | None = None
    state: EveStructureState | None = None
    type: EveStructureType | None = None
    timer: datetime | None = None
    system_name: str | None = None
    corporation_name: str | None = None
    alliance_name: str | None = None
    fitting: str | None = None
    # Why, for the audit log; not stored on the timer.
    reason: str | None = None


class EveStructurePingResponse(BaseModel):
    """A structure ping the bot sent (or failed to send) to Discord"""

    id: int
    notification_type: str
    summary: str
    discord_success: bool
    structure_id: int | None = None
    created_at: datetime | None = None
    event_time: datetime | None = None


def _audit(user, summary: str) -> None:
    AuditEntry.objects.create(
        user=user, category="other", summary=summary[:255]
    )


def _timer_response(timer: EveStructureTimer) -> dict:
    return {
        "id": timer.id,
        "name": timer.name,
        "state": timer.state,
        "type": timer.type,
        "timer": timer.timer,
        "created_at": timer.created_at,
        "updated_at": timer.updated_at,
        "created_by": timer.created_by_id,
        "updated_by": timer.updated_by_id,
        "system_name": timer.system_name,
        "corporation_name": timer.corporation_name,
        "alliance_name": timer.alliance_name,
        "structure_id": timer.structure_id,
        "campaign_id": timer.campaign_id,
        "fitting": timer.fitting,
    }


def _timer_label(timer: EveStructureTimer) -> str:
    return f"timer {timer.id} ({timer.system_name} - {timer.name})"


def _with_reason(summary: str, reason: str | None) -> str:
    reason = (reason or "").strip()
    return f"{summary}. Reason: {reason}" if reason else summary


@router.patch(
    "/timers/{timer_id}",
    auth=AuthBearer(),
    response={
        200: EveStructureTimerResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    summary="Correct a structure timer (recorded in the audit log)",
)
def update_structure_timer(
    request, timer_id: int, payload: EveStructureTimerPatch
):
    if not can_use_feature(request.user, CORRECT_FEATURE):
        return 403, ErrorResponse(detail="Permission denied")
    timer = EveStructureTimer.objects.filter(id=timer_id).first()
    if timer is None:
        return 404, ErrorResponse(detail="Timer does not exist")

    changes = payload.dict(exclude_unset=True)
    reason = changes.pop("reason", None)
    for field in ("name", "system_name"):
        if field in changes and not (changes[field] or "").strip():
            return 400, ErrorResponse(detail=f"{field} cannot be empty")
    if "timer" in changes and changes["timer"] is None:
        return 400, ErrorResponse(detail="timer cannot be empty")

    changed = []
    for field, value in changes.items():
        if isinstance(value, Enum):
            value = value.value
        if isinstance(value, str):
            value = value.strip()
        if field in ("alliance_name", "corporation_name", "fitting"):
            value = value or None
        if getattr(timer, field) != value:
            changed.append(f"{field} {getattr(timer, field)!r} -> {value!r}")
            setattr(timer, field, value)
    if changed:
        timer.updated_by = request.user
        timer.updated_at = datetime.now()
        timer.save()
        _audit(
            request.user,
            _with_reason(
                f"Corrected {_timer_label(timer)}: {'; '.join(changed)}",
                reason,
            ),
        )
    return _timer_response(timer)


@router.delete(
    "/timers/{timer_id}",
    auth=AuthBearer(),
    response={204: None, 403: ErrorResponse, 404: ErrorResponse},
    summary="Delete a wrong structure timer (recorded in the audit log)",
)
def delete_structure_timer(request, timer_id: int, reason: str | None = None):
    if not can_use_feature(request.user, CORRECT_FEATURE):
        return 403, ErrorResponse(detail="Permission denied")
    timer = EveStructureTimer.objects.filter(id=timer_id).first()
    if timer is None:
        return 404, ErrorResponse(detail="Timer does not exist")
    label = _timer_label(timer)
    when = timer.timer
    timer.delete()
    _audit(
        request.user,
        _with_reason(
            f"Deleted {label}, was due {when:%Y-%m-%d %H:%M}", reason
        ),
    )
    return 204, None


@router.get(
    "/pings",
    auth=AuthBearer(),
    response={200: List[EveStructurePingResponse], 403: ErrorResponse},
    summary="Recent structure pings and whether Discord took them",
)
def get_structure_pings(
    request,
    failed_only: bool = False,
    notification_type: str | None = None,
    limit: int = 100,
):
    if not can_use_feature(request.user, CORRECT_FEATURE):
        return 403, ErrorResponse(detail="Permission denied")
    pings = EveStructurePing.objects.order_by("-created_at", "-id")
    if failed_only:
        pings = pings.filter(discord_success=False)
    if notification_type:
        pings = pings.filter(notification_type=notification_type)
    return [
        {
            "id": ping.id,
            "notification_type": ping.notification_type,
            "summary": ping.summary,
            "discord_success": ping.discord_success,
            "structure_id": ping.structure_id,
            "created_at": ping.created_at,
            "event_time": ping.event_time,
        }
        for ping in pings[: max(1, min(limit, 500))]
    ]
