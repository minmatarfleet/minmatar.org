"""GET "/{task_id}" - one task with its comments."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import visible_task
from taskboard.queries import task_detail
from taskboard.schemas import TaskDetailResponse

PATH = "/{int:task_id}"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {200: TaskDetailResponse, 404: ErrorResponse},
    "auth": AuthBearer(),
    "summary": "One task with its comments",
}


def get_task(request, task_id: int):
    task = visible_task(request.user, task_id)
    if task is None:
        return 404, ErrorResponse(detail="Task not found.")
    return 200, task_detail(request.user, task)
