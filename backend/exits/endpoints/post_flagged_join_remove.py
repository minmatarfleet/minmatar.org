"""POST "/flagged-joins/{join_id}/remove" - the CEO's answer to a flagged join."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from exits.endpoints.schemas import FlaggedJoinResultResponse
from exits.helpers.answers import AnswerError
from exits.helpers.joins import expect_removal
from exits.models import FlaggedJoin

PATH = "/flagged-joins/{int:join_id}/remove"
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
    "summary": "Say a flagged pilot will be removed in game (CEO only)",
}


def post_flagged_join_remove(request, join_id: int):
    join = (
        FlaggedJoin.objects.select_related("corporation")
        .filter(pk=join_id)
        .first()
    )
    if join is None:
        return 404, ErrorResponse(detail="Not found")
    try:
        expect_removal(request.user, join)
    except AnswerError as error:
        return error.status_code, ErrorResponse(detail=error.message)
    return 200, {
        "id": join.pk,
        "outcome": join.outcome,
        "removal_expected": join.removal_expected_at is not None,
    }
