"""POST "/{task_id}/actions/{action}" - done, snooze, take, thank..."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import visible_task
from taskboard.queries import serialize_tasks
from taskboard.schemas import TaskResponse
from taskboard.services import ACTIONS, TaskError

PATH = "/{int:task_id}/actions/{action}"
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {
        200: TaskResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Act on a task: done, snooze, not_now, bring_back, hand_back, "
    "take, keep, let_close or thank",
}


def post_task_action(request, task_id: int, action: str):
    handler = ACTIONS.get(action)
    if handler is None:
        return 400, ErrorResponse(
            detail=f"action must be one of {', '.join(ACTIONS)}"
        )
    task = visible_task(request.user, task_id)
    if task is None:
        return 404, ErrorResponse(detail="Task not found.")
    try:
        handler(request.user, task)
    except TaskError as error:
        return error.status_code, ErrorResponse(detail=str(error))
    task.refresh_from_db()
    return 200, serialize_tasks([task], request.user)[0]
