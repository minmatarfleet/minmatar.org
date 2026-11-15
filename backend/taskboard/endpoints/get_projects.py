"""GET "/projects" - open and finished projects, and templates."""

from authentication import AuthBearer
from taskboard.queries import projects_list
from taskboard.schemas import ProjectsResponse

PATH = "/projects"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks - Projects"],
    "response": {200: ProjectsResponse},
    "auth": AuthBearer(),
    "summary": "Projects this user can see and the templates to start from",
}


def get_projects(request):
    return 200, projects_list(request.user)
