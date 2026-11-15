"""GET "/teams/{kind}/{team_id}" - one corporation, tribe or group."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.queries import team_detail
from taskboard.schemas import TeamDetailResponse

PATH = "/teams/{kind}/{int:team_id}"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {200: TeamDetailResponse, 404: ErrorResponse},
    "auth": AuthBearer(),
    "summary": "A team's leader tasks and its members' tasks by kind",
}


def get_team(request, kind: str, team_id: int):
    detail = team_detail(request.user, kind, team_id)
    if detail is None:
        return 404, ErrorResponse(detail="Team not found.")
    return 200, detail
