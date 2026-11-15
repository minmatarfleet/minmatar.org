"""GET "/projects/{project_id}" - stages, tasks, updates and people."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import visible_project
from taskboard.queries import project_detail
from taskboard.schemas import ProjectDetailResponse

PATH = "/projects/{int:project_id}"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks - Projects"],
    "response": {200: ProjectDetailResponse, 404: ErrorResponse},
    "auth": AuthBearer(),
    "summary": "One project",
}


def get_project(request, project_id: int):
    project = visible_project(request.user, project_id)
    if project is None:
        return 404, ErrorResponse(detail="Project not found.")
    return 200, project_detail(request.user, project)
