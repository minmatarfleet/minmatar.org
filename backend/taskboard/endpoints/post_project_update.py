"""POST "/projects/{project_id}/updates" - the lead's status update."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import visible_project
from taskboard.queries import project_detail
from taskboard.schemas import ProjectDetailResponse, ProjectUpdateRequest
from taskboard.services import TaskError, post_update

PATH = "/projects/{int:project_id}/updates"
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Tasks - Projects"],
    "response": {
        200: ProjectDetailResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Post a project update: on track, at risk or off track",
}


def post_project_update(
    request, project_id: int, payload: ProjectUpdateRequest
):
    project = visible_project(request.user, project_id)
    if project is None:
        return 404, ErrorResponse(detail="Project not found.")
    try:
        post_update(request.user, project, payload.health, payload.body)
    except TaskError as error:
        return error.status_code, ErrorResponse(detail=str(error))
    return 200, project_detail(request.user, project)
