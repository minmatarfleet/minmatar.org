"""GET "/corporations/{corporation_id}/members/{character_id}/history" - leadership."""

from dataclasses import asdict

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveCharacter, EveCorporation
from exits.endpoints.schemas import HistoryEntryResponse
from exits.helpers.history import history_for
from exits.helpers.joins import can_lead

PATH = "/corporations/{int:corporation_id}/members/{int:character_id}/history"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Exits"],
    "response": {
        200: list[HistoryEntryResponse],
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "A member's alliance history (the corporation's CEO and directors)",
}


def get_member_history(request, corporation_id: int, character_id: int):
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    character = EveCharacter.objects.filter(
        character_id=character_id, corporation_id=corporation_id
    ).first()
    if corporation is None or character is None:
        return 404, ErrorResponse(detail="Member not found")
    if not can_lead(request.user, corporation):
        return 403, ErrorResponse(
            detail="Only the corporation's leadership can see this"
        )
    return 200, [
        asdict(e) for e in history_for(character.user, [character_id])
    ]
