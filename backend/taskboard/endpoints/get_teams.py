"""GET "/teams" - the corporations and tribes this user leads."""

from authentication import AuthBearer
from taskboard.queries import team_overview
from taskboard.schemas import TeamOverviewResponse

PATH = "/teams"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {200: TeamOverviewResponse},
    "auth": AuthBearer(),
    "summary": "Open and closed-this-week counts for each team this user leads",
}


def get_teams(request):
    return 200, team_overview(request.user)
