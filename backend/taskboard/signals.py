"""Re-run a team rule as soon as a row it watches changes.

Each team rule names the models its collector reads (``Rule.watch``).
Saving or deleting one of those rows queues ``sync_task_rule`` for that
rule after the transaction commits, so "Review 2 requests to join Dreads"
closes a moment after the chief handles them, not at the next 15-minute
sync. Bulk ``update()`` and ``bulk_create`` send no signals; the scheduled
sync still catches those.
"""

from __future__ import annotations

import logging
from functools import partial

from django.db import connection, transaction
from django.db.models.signals import post_delete, post_save

from taskboard.models import Task
from taskboard.rules import RULES
from taskboard.tasks import sync_task_rule

logger = logging.getLogger(__name__)

_ready = False


def _taskboard_ready() -> bool:
    """False while a fresh database migrates: data migrations that import
    real models save watched rows before the taskboard tables exist."""
    global _ready  # pylint: disable=global-statement
    if not _ready:
        _ready = Task._meta.db_table in connection.introspection.table_names()
    return _ready


def queue_rule_sync(code: str) -> None:
    try:
        sync_task_rule.delay(code)
    except Exception:  # pylint: disable=broad-except
        # A broker hiccup must not fail the save that triggered it; the
        # scheduled sync closes the task a few minutes later instead.
        logger.exception("Could not queue task rule %s", code)


def is_task_refresh(callback) -> bool:
    """For tests that count on-commit callbacks: is this one ours?"""
    return getattr(callback, "func", None) is queue_rule_sync


def other_callbacks(callbacks) -> list:
    """The on-commit callbacks that aren't a task list refresh."""
    return [c for c in callbacks if not is_task_refresh(c)]


def _changed(code: str, raw: bool = False, **_kwargs) -> None:
    if raw or not _taskboard_ready():
        return  # fixtures load raw rows; the scheduled sync covers them
    transaction.on_commit(partial(queue_rule_sync, code))


def connect() -> None:
    for code, rule in RULES.items():
        if rule.is_pilot_rule:
            # Pilot rules refresh when the pilot opens their list.
            continue
        for model in rule.watch:
            receiver = partial(_changed, code)
            uid = f"taskboard-watch:{code}:{model._meta.label}"
            post_save.connect(
                receiver, sender=model, weak=False, dispatch_uid=uid
            )
            post_delete.connect(
                receiver, sender=model, weak=False, dispatch_uid=f"{uid}:del"
            )
