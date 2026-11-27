"""POST "/flagged-joins/{join_id}/keep" - the CEO's answer to a flagged join."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from exits.endpoints.schemas import (
    FlaggedJoinKeepRequest,
    FlaggedJoinResultResponse,
)
from exits.helpers.answers import AnswerError
from exits.helpers.joins import keep
from exits.models import FlaggedJoin

PATH = "/flagged-joins/{int:join_id}/keep"
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Exits"],
    "response": {
        200: FlaggedJoinResultResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Keep a flagged pilot, with a note (CEO only)",
}


def post_flagged_join_keep(
    request, join_id: int, payload: FlaggedJoinKeepRequest
):
    join = (
        FlaggedJoin.objects.select_related("corporation")
        .filter(pk=join_id)
        .first()
    )
    if join is None:
        return 404, ErrorResponse(detail="Not found")
    try:
        keep(request.user, join, payload.note)
    except AnswerError as error:
        return error.status_code, ErrorResponse(detail=error.message)
    return 200, {
        "id": join.pk,
        "outcome": join.outcome,
        "removal_expected": join.removal_expected_at is not None,
    }
