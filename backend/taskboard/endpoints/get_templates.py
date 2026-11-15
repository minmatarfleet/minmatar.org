"""GET "/templates" - project templates with their tasks."""

from authentication import AuthBearer
from taskboard.models import ProjectTemplate
from taskboard.schemas import ProjectTemplateResponse

PATH = "/templates"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks - Settings"],
    "response": {200: list[ProjectTemplateResponse]},
    "auth": AuthBearer(),
    "summary": "Project templates: stages, tasks and who gets each",
}


def get_templates(request):
    rows = []
    for template in ProjectTemplate.objects.filter(
        active=True
    ).prefetch_related("tasks"):
        tasks = list(template.tasks.all())
        rows.append(
            {
                "id": template.pk,
                "kind": template.kind,
                "name": template.name,
                "description": template.description,
                "task_count": len(tasks),
                "tasks": [
                    {
                        "id": task.pk,
                        "stage": task.stage,
                        "title": task.title,
                        "goes_to": task.goes_to,
                        "offset_days": task.offset_days,
                        "recurrence": task.recurrence,
                    }
                    for task in tasks
                ],
            }
        )
    return 200, rows
