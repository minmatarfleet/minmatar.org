"""POST "/corporations/{corporation_id}/departures/answers" - why they left."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveCorporation
from exits.endpoints.schemas import (
    DepartureAnswerRequest,
    DepartureGroupResponse,
)
from exits.helpers.answers import AnswerError, answer
from exits.helpers.listing import STATE_ALL, departure_groups

PATH = "/corporations/{int:corporation_id}/departures/answers"
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Exits"],
    "response": {
        200: list[DepartureGroupResponse],
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Say why pilots left, for one row or many (CEO only)",
}


def post_departure_answers(
    request, corporation_id: int, payload: DepartureAnswerRequest
):
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    try:
        answer(
            request.user,
            corporation,
            payload.departure_ids,
            reason=payload.reason,
            can_rejoin=payload.can_rejoin,
            note=payload.note,
        )
    except AnswerError as error:
        return error.status_code, ErrorResponse(detail=error.message)
    ids = set(payload.departure_ids)
    return 200, [
        row
        for row in departure_groups(corporation, STATE_ALL)
        if ids & set(row["departure_ids"])
    ]
