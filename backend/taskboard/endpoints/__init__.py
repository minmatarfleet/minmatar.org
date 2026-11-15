"""/api/tasks: My tasks, teams, projects and task settings.

Every endpoint registers on this one Router: GET and POST share paths
(/projects, /preferences), which separate routers cannot.
"""

from ninja import Router

from taskboard.endpoints import (
    get_my_tasks,
    get_my_task_count,
    get_teams,
    get_team,
    get_team_rule,
    post_team_rule_remind,
    get_assignees,
    get_projects,
    post_project,
    get_project,
    post_project_update,
    post_project_finish,
    get_rules,
    patch_rule,
    get_templates,
    get_digest,
    patch_digest,
    get_preferences,
    patch_preferences,
    post_task,
    get_task,
    post_task_action,
    post_task_comment,
)

router = Router(tags=["Tasks"])

# Fixed paths before /{task_id}.
for module in (
    get_my_tasks,
    get_my_task_count,
    get_teams,
    get_team,
    get_team_rule,
    post_team_rule_remind,
    get_assignees,
    get_projects,
    post_project,
    get_project,
    post_project_update,
    post_project_finish,
    get_rules,
    patch_rule,
    get_templates,
    get_digest,
    patch_digest,
    get_preferences,
    patch_preferences,
    post_task,
    get_task,
    post_task_action,
    post_task_comment,
):
    handler = getattr(module, module.__name__.rsplit(".", 1)[1])
    getattr(router, module.METHOD)(module.PATH, **module.ROUTE_SPEC)(handler)

__all__ = ["router"]
