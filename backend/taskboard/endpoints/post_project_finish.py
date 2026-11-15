"""POST "/projects/{project_id}/finish" - close a project."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import visible_project
from taskboard.queries import project_detail
from taskboard.schemas import ProjectDetailResponse
from taskboard.services import TaskError, finish_project

PATH = "/projects/{int:project_id}/finish"
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Tasks - Projects"],
    "response": {
        200: ProjectDetailResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Finish a project; its open tasks close",
}


def post_project_finish(request, project_id: int):
    project = visible_project(request.user, project_id)
    if project is None:
        return 404, ErrorResponse(detail="Project not found.")
    try:
        finish_project(request.user, project)
    except TaskError as error:
        return error.status_code, ErrorResponse(detail=str(error))
    return 200, project_detail(request.user, project)
