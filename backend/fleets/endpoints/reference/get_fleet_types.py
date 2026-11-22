"""GET /types — fleet type enum values for fleet creation UI."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.endpoints.schemas import EveFleetType
from fleets.helpers.fleet_form_access import (
    can_create_alliance_fleets,
    fleet_form_denied,
)
from fleets.helpers.schedule_fleet import GROUP_FLEET_TYPES

PATH = "/types"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetType], 403: ErrorResponse},
    "description": (
        "The fleet types the fleet form offers. Needs fleets.create, or "
        "the right to schedule fleets for a tribe group, which gets only "
        "the group fleet types (non-strategic, training, NPSI)."
    ),
}

FLEET_FORM_TYPES = [
    EveFleetType.STRATEGIC,
    EveFleetType.NON_STRATEGIC,
    EveFleetType.TRAINING,
    EveFleetType.NPSI,
]


def get_fleet_types(request):
    denied = fleet_form_denied(request.user)
    if denied:
        return denied
    if can_create_alliance_fleets(request.user):
        return FLEET_FORM_TYPES
    return [
        fleet_type
        for fleet_type in FLEET_FORM_TYPES
        if fleet_type.value in GROUP_FLEET_TYPES
    ]
