"""Sentry setup for every backend process, and the task signals it reads.

One ``init_sentry`` for the web app, beat and the workers, so they share
sampling, filters and integrations. Beat and workers report to the Celery
project (``SENTRY_CELERY_DSN``, falling back to ``SENTRY_BACKEND_DSN``):
beat opens each cron check-in and the worker closes it, so both must talk
to the same project.

Sampling is tuned for a free plan and overridable per environment without
a code change:

- ``SENTRY_TRACES_SAMPLE_RATE`` (0.2): web requests and tasks.
- ``SENTRY_TICK_TRACES_SAMPLE_RATE`` (0.02): beat entries that run every
  minute or faster (zKill poll, fleet tracking, structure notifications).
- ``SENTRY_PROFILES_SAMPLE_RATE`` (0.1): share of traced transactions that
  are also profiled.
- ``SENTRY_LOGS_LEVEL`` (WARNING): lowest log level shipped to Sentry Logs.

Errors are not sampled: every exception and every ``logger.error`` is sent.

Cron monitors: beat check-ins go only to the schedules in
``CRON_MONITORED_SCHEDULES``; each monitor counts against the plan.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from functools import lru_cache

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)

# Beat schedule names (keys of CELERYBEAT_SCHEDULE) that get a Sentry cron
# monitor. Queue health is first: it runs every minute on the fast lane, so
# a missed check-in means beat or the fast-lane workers are down or stuck.
CRON_MONITORED_SCHEDULES = (
    "[Queues] Monitor queue health",
    "[Campaigns] Close the week",
    "[Campaigns] Generate daily orders",
    "[Characters] Update Characters (assets, skills, killmails)",
    "[Market] Fetch Market Item History",
)

# Error events carry the queue as a tag, so issues can be filtered by
# queue. (Spans already get messaging.destination.name from the SDK.)
QUEUE_TAG = "celery.queue"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_level(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    level = logging.getLevelName(value.upper())
    return level if isinstance(level, int) else default


def detect_component(argv=None) -> str:
    """ "beat", "worker" or "web", from the process command line."""
    argv = sys.argv if argv is None else argv
    if any(arg == "beat" for arg in argv[1:]):
        return "beat"
    if any(arg == "worker" for arg in argv[1:]):
        return "worker"
    return "web"


def dsn_for(component: str) -> str:
    backend = os.environ.get("SENTRY_BACKEND_DSN", "")
    if component in ("beat", "worker"):
        return os.environ.get("SENTRY_CELERY_DSN") or backend
    return backend


def init_sentry(
    component: str | None = None,
    dsn: str | None = None,
    environment: str | None = None,
):
    component = component or detect_component()
    sentry_sdk.init(
        dsn=dsn_for(component) if dsn is None else dsn,
        environment=environment or os.environ.get("ENV", "production"),
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(
                monitor_beat_tasks=True,
                exclude_beat_tasks=[unmonitored_schedules_pattern()],
            ),
            LoggingIntegration(
                sentry_logs_level=_env_level(
                    "SENTRY_LOGS_LEVEL", logging.WARNING
                )
            ),
        ],
        traces_sampler=traces_sampler,
        profiles_sample_rate=_env_float("SENTRY_PROFILES_SAMPLE_RATE", 0.1),
        enable_logs=True,
        before_send=before_send,
    )
    sentry_sdk.get_global_scope().set_tag("component", component)


def unmonitored_schedules_pattern() -> str:
    """One regex matching every schedule name not in the monitored list.

    The SDK treats ``exclude_beat_tasks`` as a block list; this inverts it.
    """
    names = "|".join(re.escape(name) for name in CRON_MONITORED_SCHEDULES)
    return f"^(?!(?:{names})$).*"


@lru_cache(maxsize=1)
def tick_task_names() -> frozenset[str]:
    """Tasks beat runs every minute or faster."""
    # pylint: disable=import-outside-toplevel
    from celery.schedules import crontab, schedule
    from django.conf import settings

    names = set()
    for entry in getattr(settings, "CELERYBEAT_SCHEDULE", {}).values():
        every = entry["schedule"]
        if isinstance(every, crontab):
            fast = len(every.minute) == 60 and len(every.hour) == 24
        elif isinstance(every, schedule):
            fast = every.run_every.total_seconds() <= 60
        else:
            fast = False
        if fast:
            names.add(entry["task"])
    return frozenset(names)


def traces_sampler(sampling_context: dict) -> float:
    parent = sampling_context.get("parent_sampled")
    if parent is not None:
        return float(parent)
    rate = _env_float("SENTRY_TRACES_SAMPLE_RATE", 0.2)
    job = sampling_context.get("celery_job")
    if job and job.get("task") in tick_task_names():
        return _env_float("SENTRY_TICK_TRACES_SAMPLE_RATE", 0.02)
    return rate


def before_send(event, hint):
    """Drop known noise before it counts against the error quota.

    django-esi logs ERROR "Refresh impossible..." when a token was revoked,
    then raises TokenInvalidError; refresh_or_delete deletes the token.
    """
    del hint
    if event.get("logger") != "esi.models":
        return event
    logentry = event.get("logentry") or {}
    message = logentry.get("message") or event.get("message") or ""
    if isinstance(message, str) and message.startswith("Refresh impossible"):
        return None
    return event


def tag_task_run(request) -> None:
    """Tag the task's Sentry scope with the queue it came from."""
    queue = (getattr(request, "delivery_info", None) or {}).get("routing_key")
    if queue:
        sentry_sdk.set_tag(QUEUE_TAG, queue)


def record_task_skip(task_name: str, reason: str) -> None:
    """Count deduped or skipped task copies (Sentry metric)."""
    try:
        sentry_sdk.metrics.count(
            "celery.task.skipped",
            1,
            attributes={"task": task_name, "reason": reason},
        )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.debug("Could not record skip metric", exc_info=True)


def gauge(name: str, value: float, unit: str | None = None, **attributes):
    try:
        sentry_sdk.metrics.gauge(name, value, unit=unit, attributes=attributes)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.debug("Could not record gauge %s", name, exc_info=True)
