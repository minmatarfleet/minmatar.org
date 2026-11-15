"""Small lookups shared by the endpoints."""

from typing import Optional

from groups.helpers.feature_access import can_use_feature
from taskboard.models import Project, Task
from taskboard.queries import visible_projects
from taskboard.services import can_see

FEATURE_MANAGE = "tasks.manage"


def can_manage_settings(user) -> bool:
    """Automatic-task settings and project templates."""
    return bool(user and user.is_superuser) or can_use_feature(
        user, FEATURE_MANAGE
    )


def visible_task(user, task_id: int) -> Optional[Task]:
    task = (
        Task.objects.select_related("project", "stage", "waiting_on")
        .filter(pk=task_id)
        .first()
    )
    if task is None or not can_see(user, task):
        return None
    return task


def visible_project(user, project_id: int) -> Optional[Project]:
    return visible_projects(user).filter(pk=project_id).first()
