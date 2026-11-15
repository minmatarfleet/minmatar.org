"""POST "/projects" - start a project, from a template or blank."""

from django.contrib.auth.models import User

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.models import ProjectTemplate
from taskboard.queries import project_detail
from taskboard.schemas import ProjectCreateRequest, ProjectDetailResponse
from taskboard.services import TaskError, create_project

PATH = "/projects"
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Tasks - Projects"],
    "response": {
        201: ProjectDetailResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Start a project; a template fills in its stages and tasks",
}


def post_project(request, payload: ProjectCreateRequest):
    template = None
    if payload.template_id:
        template = ProjectTemplate.objects.filter(
            pk=payload.template_id, active=True
        ).first()
        if template is None:
            return 404, ErrorResponse(detail="Template not found.")
    lead = request.user
    if payload.lead_id:
        lead = User.objects.filter(pk=payload.lead_id).first()
        if lead is None:
            return 404, ErrorResponse(detail="Lead not found.")
    try:
        project = create_project(
            request.user,
            name=payload.name,
            lead=lead,
            template=template,
            starts_on=payload.starts_on,
            target_date=payload.target_date,
            link_url=payload.link_url,
        )
    except TaskError as error:
        return error.status_code, ErrorResponse(detail=str(error))
    return 201, project_detail(request.user, project)
