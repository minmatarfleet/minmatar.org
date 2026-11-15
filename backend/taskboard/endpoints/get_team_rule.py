"""GET "/teams/{kind}/{team_id}/rules/{rule}" - the pilots behind a count."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.queries import team_rule_pilots
from taskboard.schemas import TeamRulePilotResponse

PATH = "/teams/{kind}/{int:team_id}/rules/{rule}"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {200: list[TeamRulePilotResponse], 404: ErrorResponse},
    "auth": AuthBearer(),
    "summary": "Which members have one kind of task waiting (never suggestions)",
}


def get_team_rule(request, kind: str, team_id: int, rule: str):
    pilots = team_rule_pilots(request.user, kind, team_id, rule)
    if pilots is None:
        return 404, ErrorResponse(detail="Not found.")
    return 200, pilots
