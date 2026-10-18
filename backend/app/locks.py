"""Cross-process locks for Celery work that must not overlap.

``single_flight`` is a context manager around ``cache.add``: the first caller
gets the lock, a concurrent caller is told to skip. The lock holds an owner
token, so a run that outlives its TTL never deletes the lock of the run
that replaced it. ``overlap_guard`` wraps a task with it.

If the cache is down the lock can't be checked, so the work runs unguarded
(as it did before the guard existed) rather than not at all.

Other lock-like idioms in the codebase are deliberately different and stay
as they are: QueueOnce (dedupes at queue time; eveuniverse needs it),
cooldown markers that are never released (e.g. contract item scheduling,
LP name lookups, fleet nudges), rate windows, and the queue-on-miss locks
inside ``app.cache.CachedRollup``.
"""

from __future__ import annotations

import functools
import logging
import uuid
from contextlib import contextmanager

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
