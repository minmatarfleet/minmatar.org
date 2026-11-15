"""Keep automatic tasks in step with what they are about.

``sync_rule`` opens a task for each new thing a rule collects, refreshes
the ones still there and closes the ones that are gone. ``sweep`` handles
time: suggestions that sat too long stop asking, quiet claims return to
the team, and assigned tasks nobody touches ask their author once whether
they are still needed. Both are safe to run twice.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from taskboard.models import Task, TaskRuleSetting, Weight
from taskboard.rules import RULES, Item, Rule, claim_expiry, stop_after

logger = logging.getLogger(__name__)

# Assigned tasks with no activity for this long ask their author once.
STILL_NEEDED_AFTER = timedelta(days=30)
# ...and close this long after asking if nobody answers.
STILL_NEEDED_GRACE = timedelta(days=14)

REFRESHED_FIELDS = (
    "title",
    "detail",
    "link_url",
    "link_label",
    "team_label",
)


def _settings() -> dict[str, TaskRuleSetting]:
    return {row.rule: row for row in TaskRuleSetting.objects.all()}


def _key(task_or_item) -> tuple:
    """Team tasks match on the thing alone: a claim sets ``user``."""
    if task_or_item.team_kind:
        return (task_or_item.source_key, None)
    return (task_or_item.source_key, task_or_item.user_id)


def sync_rule(
    rule: Rule,
    user_ids: Optional[set[int]] = None,
    setting: Optional[TaskRuleSetting] = None,
    now=None,
) -> dict:
    """Open, refresh and close one rule's tasks. Returns counts."""
    now = now or timezone.now()
    counts = {"opened": 0, "reopened": 0, "closed": 0}
    existing_qs = Task.objects.filter(kind=Task.KIND_AUTOMATIC, rule=rule.code)
    if user_ids is not None:
        if not rule.is_pilot_rule:
            return counts
        existing_qs = existing_qs.filter(user_id__in=user_ids)

    if setting is not None and not setting.enabled:
        counts["closed"] = existing_qs.filter(status=Task.STATUS_OPEN).update(
            status=Task.STATUS_CANCELLED,
            closed_at=now,
            close_note="This task was turned off",
        )
        return counts

    items: dict[tuple, Item] = {}
    for item in rule.collect(user_ids):
        items.setdefault(_key(item), item)

    existing: dict[tuple, Task] = {}
    for task in existing_qs.order_by("id"):
        existing[_key(task)] = task

    with transaction.atomic():
        for key, item in items.items():
            task = existing.get(key)
            if task is None:
                Task.objects.create(
                    kind=Task.KIND_AUTOMATIC,
                    rule=rule.code,
                    source_key=item.source_key,
                    title=item.title,
                    detail=item.detail,
                    link_url=item.link_url,
                    link_label=item.link_label,
                    weight=rule.weight,
                    user_id=item.user_id,
                    team_kind=item.team_kind,
                    team_id=item.team_id,
                    team_role=item.team_role,
                    team_label=item.team_label,
                    when=(
                        Task.WHEN_THIS_WEEK
                        if rule.weight == Weight.NEEDS_YOU
                        else Task.WHEN_NO_RUSH
                    ),
                    opened_at=item.since or now,
                    last_activity_at=now,
                )
                counts["opened"] += 1
                continue
            changed = [
                name
                for name in REFRESHED_FIELDS
                if getattr(task, name) != getattr(item, name)
            ]
            for name in changed:
                setattr(task, name, getattr(item, name))
            if task.status in (Task.STATUS_DONE, Task.STATUS_CANCELLED):
                # The thing came back (a token broke again).
                task.status = Task.STATUS_OPEN
                task.opened_at = item.since or now
                task.last_activity_at = now
                task.closed_at = None
                task.close_note = ""
                task.snoozed_until = None
                if task.team_kind:
                    task.user_id = None
                    task.claimed_at = None
                changed += [
                    "status",
                    "opened_at",
                    "last_activity_at",
                    "closed_at",
                    "close_note",
                    "snoozed_until",
                    "user",
                    "claimed_at",
                ]
                counts["reopened"] += 1
            if changed:
                task.save(update_fields=sorted(set(changed)))

        gone = [
            task.pk
            for key, task in existing.items()
            if key not in items and task.status == Task.STATUS_OPEN
        ]
        if gone:
            counts["closed"] = Task.objects.filter(pk__in=gone).update(
                status=Task.STATUS_DONE,
                closed_at=now,
                last_activity_at=now,
                close_note="Closed by itself",
            )
    return counts


def sync_all(now=None) -> dict:
    settings = _settings()
    totals = {}
    for code, rule in RULES.items():
        try:
            totals[code] = sync_rule(rule, setting=settings.get(code), now=now)
        except Exception:  # pylint: disable=broad-except
            # One broken source must not stop the others.
            logger.exception("Task rule %s failed", code)
    return totals


def sync_user(user, now=None) -> None:
    """Refresh one pilot's own automatic tasks (when they open the list)."""
    settings = _settings()
    for rule in RULES.values():
        if rule.is_pilot_rule:
            sync_rule(
                rule,
                user_ids={user.pk},
                setting=settings.get(rule.code),
                now=now,
            )


def sweep(now=None) -> dict:
    """Time-based closes: stop asking, return claims, ask "still needed?"."""
    now = now or timezone.now()
    settings = _settings()
    counts = {"stopped": 0, "released": 0, "asked": 0, "expired": 0}

    for code, rule in RULES.items():
        setting = settings.get(code)
        window = stop_after(rule, setting)
        if window and rule.weight == Weight.SUGGESTION:
            counts["stopped"] += Task.objects.filter(
                kind=Task.KIND_AUTOMATIC,
                rule=code,
                status=Task.STATUS_OPEN,
                opened_at__lt=now - window,
            ).update(
                status=Task.STATUS_STOPPED,
                closed_at=now,
                close_note="A suggestion that sat for " f"{window.days} days",
            )
        expiry = claim_expiry(rule, setting)
        if expiry:
            counts["released"] += _release_claims(code, expiry, now)

    # Assigned team tasks inside projects return after 14 quiet days too.
    counts["released"] += _release_claims("", timedelta(days=14), now)

    quiet = Task.objects.filter(
        kind=Task.KIND_ASSIGNED,
        status=Task.STATUS_OPEN,
        recurrence="",
    )
    counts["asked"] = quiet.filter(
        still_needed_asked_at__isnull=True,
        last_activity_at__lt=now - STILL_NEEDED_AFTER,
        created_by__isnull=False,
    ).update(still_needed_asked_at=now)
    counts["expired"] = quiet.filter(
        still_needed_asked_at__lt=now - STILL_NEEDED_GRACE,
        last_activity_at__lt=now - STILL_NEEDED_GRACE,
    ).update(
        status=Task.STATUS_STOPPED,
        closed_at=now,
        close_note="Nobody said it was still needed",
    )
    return counts


def _release_claims(rule_code: str, expiry: timedelta, now) -> int:
    return (
        Task.objects.filter(
            rule=rule_code,
            status=Task.STATUS_OPEN,
            claimed_at__isnull=False,
            last_activity_at__lt=now - expiry,
        )
        .exclude(team_kind="")
        .update(user=None, claimed_at=None, last_activity_at=now)
    )
