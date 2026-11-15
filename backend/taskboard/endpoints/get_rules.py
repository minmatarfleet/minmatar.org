"""GET "/rules" - automatic task settings."""

from django.db.models import Count

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import can_manage_settings
from taskboard.models import Task, TaskRuleSetting
from taskboard.reminders import DEFAULT_REMIND_AFTER_DAYS
from taskboard.rules import RULES
from taskboard.schemas import RuleSettingResponse


def rule_rows() -> list[dict]:
    settings = {row.rule: row for row in TaskRuleSetting.objects.all()}
    open_counts = dict(
        Task.objects.filter(kind=Task.KIND_AUTOMATIC, status=Task.STATUS_OPEN)
        .order_by()
        .values("rule")
        .annotate(n=Count("id"))
        .values_list("rule", "n")
    )
    rows = []
    for rule in RULES.values():
        setting = settings.get(rule.code)
        rows.append(
            {
                "rule": rule.code,
                "label": rule.label,
                "description": rule.description,
                "audience": rule.audience,
                "weight": rule.weight,
                "enabled": setting.enabled if setting else True,
                "stop_after_days": (
                    setting.stop_after_days
                    if setting and setting.stop_after_days
                    else rule.stop_after_days
                ),
                "claim_expires_days": (
                    setting.claim_expires_days
                    if setting and setting.claim_expires_days
                    else rule.claim_expires_days
                ),
                "remind_after_days": (
                    (
                        (setting.remind_after_days if setting else None)
                        or DEFAULT_REMIND_AFTER_DAYS
                    )
                    if rule.is_pilot_rule and rule.weight == "needs_you"
                    else None
                ),
                "open_now": open_counts.get(rule.code, 0),
            }
        )
    return rows


PATH = "/rules"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks - Settings"],
    "response": {200: list[RuleSettingResponse], 403: ErrorResponse},
    "auth": AuthBearer(),
    "summary": "Each automatic task: who gets it, whether it is on, its timers",
}


def get_rules(request):
    if not can_manage_settings(request.user):
        return 403, ErrorResponse(detail="Only task admins see this.")
    return 200, rule_rows()
