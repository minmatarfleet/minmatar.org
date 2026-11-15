"""When a leader may remind a pilot about a task (once, after it waited)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from django.utils import timezone

from taskboard.models import Task, TaskRuleSetting, Weight

DEFAULT_REMIND_AFTER_DAYS = 14


def remind_after(rule_code: str) -> timedelta:
    setting = TaskRuleSetting.objects.filter(rule=rule_code).first()
    days = (
        setting.remind_after_days
        if setting and setting.remind_after_days
        else DEFAULT_REMIND_AFTER_DAYS
    )
    return timedelta(days=days)


def can_remind(task: Task, now: Optional[datetime] = None) -> bool:
    now = now or timezone.now()
    return (
        task.status == Task.STATUS_OPEN
        and task.weight == Weight.NEEDS_YOU
        and task.reminded_at is None
        and task.user_id is not None
        and not task.team_kind
        and task.opened_at <= now - remind_after(task.rule)
    )
