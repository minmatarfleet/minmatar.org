from datetime import datetime
from enum import Enum

import requests
from pydantic import BaseModel

from app.settings import settings

API_URL = settings.API_URL
TIMERS_URL = f"{API_URL}/structures/timers"


class EveStructureState(Enum):
    ANCHORING = "anchoring"
    ARMOR = "armor"
    HULL = "hull"
    UNANCHORING = "unanchoring"


class EveStructureType(Enum):
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


class EveStructureTimerResponse(BaseModel):
    id: int
    name: str
    state: str
    type: str
    timer: datetime
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int | None = None
    system_name: str
    corporation_name: str | None = None
    alliance_name: str | None = None
    structure_id: int | None = None


class EveStructureTimerRequest(BaseModel):
    selected_item_window: str
    corporation_name: str
    state: EveStructureState
    type: EveStructureType


def get_timers():
    """
    Get timers for the bot response
    """
    response = requests.get(
        TIMERS_URL,
        headers={"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"},
        timeout=5,
    )
    response.raise_for_status()
    return [EveStructureTimerResponse(**timer) for timer in response.json()]


def submit_timer(timer: EveStructureTimerRequest):
    """
    Create a timer
    """
    body = {
        "state": timer.state.value,
        "type": timer.type.value,
        "selected_item_window": timer.selected_item_window,
        "corporation_name": timer.corporation_name,
    }
    response = requests.post(
        TIMERS_URL,
        headers={"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"},
        json=body,
        timeout=5,
    )
    response.raise_for_status()
    return response.json()
