"""POST "/teams/{kind}/{team_id}/rules/{rule}/remind/{task_id}" - remind once."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.messages import remind
from taskboard.models import Task
from taskboard.queries import team_rule_pilots
from taskboard.schemas import TeamRulePilotResponse
from taskboard.services import TaskError

PATH = "/teams/{kind}/{int:team_id}/rules/{rule}/remind/{int:task_id}"
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {
        200: list[TeamRulePilotResponse],
        400: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Remind a member about one task, once (a Discord DM)",
}


def post_team_rule_remind(
    request, kind: str, team_id: int, rule: str, task_id: int
):
    # Only a leader of the pilot's own team sees (and so reminds) them.
    pilots = team_rule_pilots(request.user, kind, team_id, rule)
    if pilots is None or not any(row["task_id"] == task_id for row in pilots):
        return 404, ErrorResponse(detail="Not found.")
    task = Task.objects.select_related("user").get(pk=task_id)
    try:
        remind(request.user, task)
    except TaskError as error:
        return error.status_code, ErrorResponse(detail=str(error))
    return 200, team_rule_pilots(request.user, kind, team_id, rule)
