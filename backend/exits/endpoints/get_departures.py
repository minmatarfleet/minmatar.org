"""GET "/corporations/{corporation_id}/departures" - the CEO's Departures tab."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveCorporation
from exits.endpoints.schemas import DepartureGroupResponse
from exits.helpers.answers import can_answer
from exits.helpers.listing import STATE_OPEN, STATES, departure_groups

PATH = "/corporations/{int:corporation_id}/departures"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Exits"],
    "response": {
        200: list[DepartureGroupResponse],
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Pilots who left a tracked corporation (CEO only)",
}


def get_departures(request, corporation_id: int, state: str = STATE_OPEN):
    if state not in STATES:
        choices = ", ".join(STATES)
        return 400, ErrorResponse(detail=f"state must be one of {choices}")
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_answer(request.user, corporation):
        return 403, ErrorResponse(
            detail="Only the corporation's CEO can see this"
        )
    return 200, departure_groups(corporation, state)
