"""How deep each Celery queue is and how long its oldest message has waited.

``measure_queues`` reads the Redis broker directly: kombu keeps each queue
as one list per priority step (``celery``, ``celery\\x06\\x163``, ...),
pushes new messages on the left and pops from the right, so the right end
of each list is the next to run. ``report_queues`` turns a measurement into
Sentry gauges, and into a Sentry warning when a queue's oldest message has
waited longer than its ``max_wait_seconds``.
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

import sentry_sdk
from django.core.cache import cache

from app import monitoring
from app.queues import QUEUES

logger = logging.getLogger(__name__)

PRIORITY_SEPARATOR = "\x06\x16"
# How many of the oldest messages per list to read for the task breakdown.
SAMPLE_SIZE = 200
ALERT_COOLDOWN_SECONDS = 15 * 60
ENQUEUED_HEADERS = ("enqueued_at", "sentry-task-enqueued-time")


@dataclass
class QueueStatus:
    name: str
    depth: int = 0
    oldest_wait: float | None = None
    oldest_tasks: Counter = field(default_factory=Counter)

    @property
    def backed_up(self) -> bool:
        spec = QUEUES[self.name]
        return (self.oldest_wait or 0) > spec.max_wait_seconds

    def as_dict(self) -> dict:
        return {
            "depth": self.depth,
            "oldest_wait": (
                None if self.oldest_wait is None else round(self.oldest_wait)
            ),
            "oldest_tasks": dict(self.oldest_tasks.most_common(5)),
        }


def priority_keys(queue: str, steps=range(10)) -> list[str]:
    return [
        queue if step == 0 else f"{queue}{PRIORITY_SEPARATOR}{step}"
        for step in steps
    ]


def message_wait(raw: bytes | str, now: float) -> float | None:
    """Seconds a message has been ready to run, or None if unknown."""
    try:
        headers = json.loads(raw).get("headers") or {}
    except (TypeError, ValueError, AttributeError):
        return None
    nested = headers.get("headers") or {}
    enqueued = None
    for name in ENQUEUED_HEADERS:
        value = headers.get(name, nested.get(name))
        if value is not None:
            try:
                enqueued = float(value)
                break
            except (TypeError, ValueError):
                continue
    if enqueued is None:
        return None
    ready = enqueued
    eta = headers.get("eta")
    if eta:
        try:
            ready = max(ready, datetime.fromisoformat(eta).timestamp())
        except (TypeError, ValueError):
            pass
    return max(now - ready, 0.0)


def _task_name(raw: bytes | str) -> str:
    try:
        return (json.loads(raw).get("headers") or {}).get("task") or "?"
    except (TypeError, ValueError, AttributeError):
        return "?"


def measure_queues(client, now: float | None = None) -> dict[str, QueueStatus]:
    """Depth and oldest wait for every declared queue."""
    now = time.time() if now is None else now
    report = {}
    for name in QUEUES:
        status = QueueStatus(name)
        for key in priority_keys(name):
            length = client.llen(key)
            if not length:
                continue
            status.depth += length
            oldest = client.lrange(key, -SAMPLE_SIZE, -1)
            status.oldest_tasks.update(_task_name(raw) for raw in oldest)
            wait = message_wait(oldest[-1], now) if oldest else None
            if wait is not None:
                status.oldest_wait = max(status.oldest_wait or 0.0, wait)
        report[name] = status
    return report


def report_queues(report: dict[str, QueueStatus], unacked: int | None) -> None:
    for status in report.values():
        monitoring.gauge("celery.queue.depth", status.depth, queue=status.name)
        if status.oldest_wait is not None:
            monitoring.gauge(
                "celery.queue.oldest_wait",
                status.oldest_wait,
                unit="second",
                queue=status.name,
            )
        if status.backed_up:
            _alert_backed_up(status)
    if unacked is not None:
        # Messages workers hold but haven't run: countdowns, rate limits.
        monitoring.gauge("celery.queue.reserved", unacked)


def _alert_backed_up(status: QueueStatus) -> None:
    spec = QUEUES[status.name]
    logger.warning(
        "Celery queue %s is backed up: %s waiting, oldest %ss (limit %ss)",
        status.name,
        status.depth,
        round(status.oldest_wait or 0),
        spec.max_wait_seconds,
    )
    try:
        first = cache.add(
            f"queue-health:alerted:{status.name}", "1", ALERT_COOLDOWN_SECONDS
        )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Alert throttle unavailable", exc_info=True)
        first = True
    if not first:
        return
    with sentry_sdk.new_scope() as scope:
        scope.fingerprint = ["celery-queue-backed-up", status.name]
        scope.set_tag(monitoring.QUEUE_TAG, status.name)
        scope.set_context(
            "queue",
            {**status.as_dict(), "max_wait_seconds": spec.max_wait_seconds},
        )
        sentry_sdk.capture_message(
            f"Celery queue {status.name} is backed up", level="warning"
        )
