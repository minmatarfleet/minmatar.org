"""POST "/flags/{flag_id}/clear" - lift a can't-rejoin flag."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from exits.endpoints.schemas import FlagClearResponse
from exits.helpers.answers import AnswerError, clear_flag
from exits.models import RejoinFlag

PATH = "/flags/{int:flag_id}/clear"
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Exits"],
    "response": {
        200: FlagClearResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Clear a can't-rejoin flag (the setting corporation's CEO)",
}


def post_flag_clear(request, flag_id: int):
    flag = (
        RejoinFlag.objects.select_related("corporation")
        .filter(pk=flag_id)
        .first()
    )
    if flag is None:
        return 404, ErrorResponse(detail="Flag not found")
    try:
        clear_flag(request.user, flag)
    except AnswerError as error:
        return error.status_code, ErrorResponse(detail=error.message)
    return 200, {"cleared": True}
