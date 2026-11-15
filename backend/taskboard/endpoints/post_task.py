"""POST "" - a leader gives someone (or a team) a task."""

from django.contrib.auth.models import User

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import visible_project
from taskboard.models import ProjectStage
from taskboard.queries import serialize_tasks
from taskboard.schemas import TaskCreateRequest, TaskResponse
from taskboard.services import TaskError, create_task
from taskboard.teams import Membership

PATH = ""
METHOD = "post"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {
        201: TaskResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Give a person or a team a task",
}


def post_task(request, payload: TaskCreateRequest):
    user = request.user
    assignee = None
    if payload.assignee_id:
        assignee = User.objects.filter(pk=payload.assignee_id).first()
        if assignee is None:
            return 404, ErrorResponse(detail="Pilot not found.")
    if payload.screen and payload.screen not in Membership(user).staff_screens:
        return 403, ErrorResponse(detail="That team isn't yours to assign.")
    project = None
    stage = None
    if payload.project_id:
        project = visible_project(user, payload.project_id)
        if project is None:
            return 404, ErrorResponse(detail="Project not found.")
        if payload.stage_id:
            stage = ProjectStage.objects.filter(
                pk=payload.stage_id, project=project
            ).first()
    try:
        task = create_task(
            user,
            title=payload.title,
            assignee=assignee,
            screen=payload.screen,
            when=payload.when,
            due_date=payload.due_date,
            body=payload.body,
            link_url=payload.link_url,
            project=project,
            stage=stage,
        )
    except TaskError as error:
        return error.status_code, ErrorResponse(detail=str(error))
    return 201, serialize_tasks([task], user)[0]
