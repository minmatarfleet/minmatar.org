"""The base class of every Celery task in the app (the app's ``task_cls``).

Every task gets these without asking:

- **One queued copy per call.** ``delay``/``apply_async`` drops a copy when
  the same task with the same arguments is already waiting in the queue.
  The lock is released when a worker starts the copy, so the next call can
  queue while it runs. It lasts the message's ``expires``, or the queue's
  ``dedupe_ttl_seconds`` (plus any countdown) when the task sets none.
- **One run per message.** Redis hands a message out again when a worker
  held it past the visibility timeout (countdowns, rate limits). A worker
  skips a message whose run already started.
- **An enqueue timestamp** in the ``enqueued_at`` header, so queue health
  can tell how long the oldest message has waited.
- **A Sentry ``celery.queue`` tag** on the run, so errors can be filtered
  by queue.

And these when the decorator asks for them:

- ``expires=<s>``: drop a copy that waited longer than this.
- ``cooldown=<s>``: skip a run when the same call started less than this
  long ago, however it was queued.
- ``exclusive=<s>``: skip a run while the same call is still running
  elsewhere. Set it to the longest expected runtime plus margin; a worker
  that dies holds it until then.
- ``dedupe=False``: queue every copy (each call is distinct work). A call
  site can also pass ``apply_async(..., dedupe=False)``.

Retries, chord and group members, linked callbacks and Celery's built-in
tasks are never deduped:
dropping one would break the retry count or leave a chord waiting forever.
Eager runs (tests) and direct calls skip all of it.

If the cache is down, every guard lets the work through, as Celery did
before the guards existed. See docs/architecture/celery-queues.md.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import time
from datetime import datetime, timezone

from celery import Task, states
from celery.result import EagerResult
from celery.utils import uuid
from django.core.cache import cache

from app import monitoring
from app.locks import single_flight
from app.queues import QUEUES, queue_for_task

logger = logging.getLogger(__name__)

ENQUEUED_AT_HEADER = "enqueued_at"
# A message can be handed out again an hour (the visibility timeout) after
# a worker reserved it, and again each hour after that while it waits.
STARTED_MARKER_TTL = 6 * 60 * 60
_NEVER_DEDUPE_OPTIONS = ("retries", "chord", "group_id", "link", "link_error")
# Celery's own plumbing (chord_unlock, group, chain): never drop a copy.
_CELERY_BUILTINS = "celery."


class AppTask(Task):
    """See the module docstring."""

    dedupe: bool = True
    cooldown: int | None = None
    exclusive: int | None = None

    # Queueing

    def apply_async(self, args=None, kwargs=None, **options):
        dedupe = options.pop("dedupe", self.dedupe)
        headers = dict(options.get("headers") or {})
        headers.setdefault(ENQUEUED_AT_HEADER, time.time())
        options["headers"] = headers

        if (
            dedupe
            and not self.app.conf.task_always_eager
            and not self.name.startswith(_CELERY_BUILTINS)
            and not any(options.get(o) for o in _NEVER_DEDUPE_OPTIONS)
        ):
            task_id = options.get("task_id") or uuid()
            options["task_id"] = task_id
            key = self.queued_key(args, kwargs)
            if not _acquire(key, task_id, self.queued_ttl(options)):
                monitoring.record_task_skip(self.name, "already queued")
                return EagerResult(None, None, states.REJECTED)
        return super().apply_async(args, kwargs, **options)

    def queued_ttl(self, options) -> int:
        expires = _seconds_from_now(options.get("expires", self.expires))
        if expires is not None:
            return max(int(expires), 1)
        queue = options.get("queue") or queue_for_task(self.name)
        queue = getattr(queue, "name", queue)
        spec = QUEUES.get(queue)
        base = spec.dedupe_ttl_seconds if spec else 60 * 60
        delay = options.get("countdown") or 0
        eta = _seconds_from_now(options.get("eta"))
        return int(base + max(delay, eta or 0, 0))

    # Running

    def __call__(self, *args, **kwargs):
        request = self.request
        if request.called_directly:
            return super().__call__(*args, **kwargs)
        if self.dedupe:
            # Our copy left the queue: let the next call queue one.
            _release(self.queued_key(args, kwargs), request.id)
        if request.is_eager:
            return super().__call__(*args, **kwargs)

        monitoring.tag_task_run(request)
        started_key = f"task-started:{request.id}:{request.retries or 0}"
        if not _acquire(started_key, "1", STARTED_MARKER_TTL):
            return self._skip("redelivered", args)
        if self.cooldown and not _acquire(
            self.call_key("task-cooldown", args, kwargs), "1", self.cooldown
        ):
            return self._skip("cooldown", args)
        if self.exclusive:
            key = self.call_key("task-running", args, kwargs)
            with single_flight(key, self.exclusive) as acquired:
                if not acquired:
                    return self._skip("still running", args)
                return super().__call__(*args, **kwargs)
        return super().__call__(*args, **kwargs)

    def _skip(self, reason: str, args) -> None:
        logger.info("Skipping %s%s: %s", self.name, tuple(args), reason)
        monitoring.record_task_skip(self.name, reason)

    # Keys

    def queued_key(self, args, kwargs) -> str:
        return self.call_key("task-queued", args, kwargs)

    def call_key(self, prefix: str, args, kwargs) -> str:
        """``prefix:task:digest`` of the call's arguments, defaults filled in,
        so ``f(1)`` and ``f(x=1)`` share a key."""
        args = tuple(args or ())
        kwargs = dict(kwargs or {})
        try:
            bound = self._run_signature().bind(*args, **kwargs)
            bound.apply_defaults()
            payload = {
                name: value
                for name, value in bound.arguments.items()
                if not isinstance(value, Task)
            }
        except TypeError:
            payload = {"args": args, "kwargs": kwargs}
        blob = json.dumps(payload, sort_keys=True, default=repr)
        digest = hashlib.sha1(blob.encode()).hexdigest()[:16]
        return f"{prefix}:{self.name}:{digest}"

    def _run_signature(self) -> inspect.Signature:
        signature = self.__dict__.get("_run_signature_cache")
        if signature is None:
            signature = inspect.signature(self.run)
            self.__dict__["_run_signature_cache"] = signature
        return signature


def _seconds_from_now(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return (value - datetime.now(timezone.utc)).total_seconds()
    return float(value)


def _acquire(key: str, value: str, ttl: int) -> bool:
    try:
        return bool(cache.add(key, value, ttl))
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Task guard unavailable for %s", key, exc_info=True)
        return True


def _release(key: str, owner: str) -> None:
    try:
        if cache.get(key) == owner:
            cache.delete(key)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Could not release %s", key, exc_info=True)
