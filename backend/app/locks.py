"""Cross-process locks for Celery work that must not overlap.

``single_flight`` is a context manager around ``cache.add``: the first caller
gets the lock, a concurrent caller is told to skip. The lock holds an owner
token, so a run that outlives its TTL never deletes the lock of the run
that replaced it. ``overlap_guard`` wraps a task with it.

``DedupedTask`` is a task base for scheduled and fanned-out work: one queued
copy per task and arguments, and a worker skips a copy whose call already
started a moment ago.

If the cache is down the lock can't be checked, so the work runs unguarded
(as it did before the guard existed) rather than not at all.

Other lock-like idioms in the codebase are deliberately different and stay
as they are: bare QueueOnce (dedupes at queue time; eveuniverse needs it),
cooldown markers that are never released (e.g. contract item scheduling,
LP name lookups, fleet nudges), rate windows, and the queue-on-miss locks
inside ``app.cache.CachedRollup``.
"""

from __future__ import annotations

import functools
import logging
import uuid
from contextlib import contextmanager

from celery_once import QueueOnce
from django.core.cache import cache

logger = logging.getLogger(__name__)


@contextmanager
def single_flight(key: str, ttl: int):
    """Yield True if this caller holds ``key``, False if another one does.

    Set ``ttl`` to the expected runtime plus margin: if a worker dies
    mid-run, the lock blocks new runs until it expires.
    """
    token = uuid.uuid4().hex
    try:
        acquired = cache.add(key, token, ttl)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Lock unavailable for %s; running", key, exc_info=True)
        yield True
        return
    if not acquired:
        yield False
        return
    try:
        yield True
    finally:
        _release(key, token)


def _release(key: str, token: str) -> None:
    try:
        if cache.get(key) == token:
            cache.delete(key)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Could not release lock %s", key, exc_info=True)


def overlap_guard(ttl: int, key: str | None = None):
    """Skip a task run (returning None) while the previous one still runs.

    Put it under ``@app.task``. The lock key defaults to the function's
    dotted path, so every run of the task shares one lock whatever its
    arguments.
    """

    def decorator(func):
        lock_key = key or f"task-lock:{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with single_flight(lock_key, ttl) as acquired:
                if not acquired:
                    logger.info(
                        "Skipping %s: the previous run still holds %s",
                        func.__qualname__,
                        lock_key,
                    )
                    return None
                return func(*args, **kwargs)

        return wrapper

    return decorator


class DedupedTask(QueueOnce):
    """One queued copy per task and arguments; stale copies skip.

    Use it as ``@app.task(base=DedupedTask, expires=..., cooldown=...)``.

    - Queueing: while a copy with the same arguments is queued or running,
      ``delay``/``apply_async`` drops the new one (QueueOnce, graceful).
      The lock lasts ``expires`` seconds, as long as the message: a copy a
      worker throws away as expired never runs, so nothing else frees it.
    - Running: a worker skips a copy when the same call started less than
      ``cooldown`` seconds ago. That drains duplicates the lock never saw:
      copies queued before it existed, and messages Redis hands out again
      after a worker held them past the visibility timeout.

    Direct calls and eager runs (tests) always run.
    """

    abstract = True
    cooldown: int | None = None

    @property
    def once(self):
        return {"graceful": True, "timeout": self.expires or 60 * 60}

    def __call__(self, *args, **kwargs):
        if self.cooldown and self._started_recently(args, kwargs):
            return None
        return super().__call__(*args, **kwargs)

    def _started_recently(self, args, kwargs) -> bool:
        request = self.request
        if request.called_directly or request.is_eager:
            return False
        key = f"task-cooldown:{self.get_key(args, kwargs)}"
        try:
            first = cache.add(key, "1", self.cooldown)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning(
                "Cooldown unavailable for %s; running", key, exc_info=True
            )
            return False
        if not first:
            logger.info(
                "Skipping %s%s: the same call started under %ss ago",
                self.name,
                tuple(args),
                self.cooldown,
            )
        return not first
