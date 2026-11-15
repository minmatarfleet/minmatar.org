"""POST "/{task_id}/comments" - add a comment."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import visible_task
from taskboard.queries import task_detail
from taskboard.schemas import TaskCommentRequest, TaskDetailResponse
from taskboard.services import TaskError, comment

PATH = "/{int:task_id}/comments"
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {
        200: TaskDetailResponse,
        400: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Comment on a task",
}


def post_task_comment(request, task_id: int, payload: TaskCommentRequest):
    task = visible_task(request.user, task_id)
    if task is None:
        return 404, ErrorResponse(detail="Task not found.")
    try:
        comment(request.user, task, payload.body)
    except TaskError as error:
        return error.status_code, ErrorResponse(detail=str(error))
    return 200, task_detail(request.user, task)
