"""GET "/corporations/{corporation_id}/flagged-joins" - for the CEO."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveCorporation
from exits.endpoints.schemas import FlaggedJoinResponse
from exits.helpers.answers import can_answer
from exits.helpers.join_rows import open_join_rows

PATH = "/corporations/{int:corporation_id}/flagged-joins"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Exits"],
    "response": {
        200: list[FlaggedJoinResponse],
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Pilots marked can't rejoin who joined this corporation (CEO only)",
}


def get_flagged_joins(request, corporation_id: int):
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_answer(request.user, corporation):
        return 403, ErrorResponse(
            detail="Only the corporation's CEO can see this"
        )
    return 200, open_join_rows(corporation)
