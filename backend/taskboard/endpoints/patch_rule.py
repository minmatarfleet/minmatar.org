"""PATCH "/rules/{rule}" - turn an automatic task on or off, set timers."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import can_manage_settings
from taskboard.endpoints.get_rules import rule_rows
from taskboard.models import TaskRuleSetting
from taskboard.rules import RULES
from taskboard.schemas import RuleSettingPatch, RuleSettingResponse

PATH = "/rules/{rule}"
METHOD = "patch"
ROUTE_SPEC = {
    "tags": ["Tasks - Settings"],
    "response": {
        200: RuleSettingResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Change one automatic task's settings",
}


def patch_rule(request, rule: str, payload: RuleSettingPatch):
    if not can_manage_settings(request.user):
        return 403, ErrorResponse(detail="Only task admins change this.")
    if rule not in RULES:
        return 404, ErrorResponse(detail="No such automatic task.")
    for days in (payload.stop_after_days, payload.claim_expires_days):
        if days is not None and not 1 <= days <= 365:
            return 400, ErrorResponse(detail="Days must be 1 to 365.")
    setting, _ = TaskRuleSetting.objects.get_or_create(rule=rule)
    for name in ("enabled", "stop_after_days", "claim_expires_days"):
        value = getattr(payload, name)
        if value is not None:
            setattr(setting, name, value)
    setting.save()
    return 200, next(row for row in rule_rows() if row["rule"] == rule)
