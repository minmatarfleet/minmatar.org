"""Cache access that degrades instead of failing, and cached rollups.

The cache is an accelerator. If Redis is down, a page renders without
cached data rather than returning a 500, so every helper here logs and
carries on when the cache raises.

Heavy rollups (scans over fleet attendance, killmails, skills, market
history) are precomputed by Celery and only read in a request; see
``CachedRollup.get_or_queue``. Light queries that are fine to run in a
request use ``CachedRollup.get_or_compute``. Each caller picks its policy
explicitly.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from django.core.cache import cache

logger = logging.getLogger(__name__)

_ERROR = object()


def cache_get(key):
    try:
        return cache.get(key)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Cache read failed for %s", key, exc_info=True)
        return None


def cache_set(key, value, timeout) -> None:
    try:
        cache.set(key, value, timeout)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Cache write failed for %s", key, exc_info=True)


def _cache_add(key, value, timeout):
    """True or False like cache.add, or _ERROR when the cache is down."""
    try:
        return cache.add(key, value, timeout)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Cache add failed for %s", key, exc_info=True)
        return _ERROR


def cache_add(key, value, timeout) -> bool:
    return _cache_add(key, value, timeout) is True


def cache_delete(key) -> None:
    try:
        cache.delete(key)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Cache delete failed for %s", key, exc_info=True)


class CachedRollup:
    """One cached rollup: a versioned key, a TTL and a refresh lock.

    ``key`` and ``lock_key`` are ``str.format`` templates filled from the
    keyword arguments of each call (unused ones are ignored, so a rollup
    refreshed in one pass can share a single lock). Bump the version in
    ``key`` whenever the cached shape changes.

    Request-path policies:

    - ``get_or_queue``: never computes. On a miss, the first caller queues
      one refresh through ``enqueue`` (``cache.add`` makes it single-flight
      across processes) and everybody gets None until the refresh lands.
      The refresh task calls ``store``, which also releases the lock.
    - ``get_or_compute``: for light queries only. On a miss one caller
      computes and stores; concurrent callers wait briefly for its result
      and compute themselves only if it doesn't arrive.
    """

    def __init__(
        self,
        *,
        key: str,
        ttl: int,
        lock_key: str,
        lock_ttl: int,
        enqueue: Callable[..., None] | None = None,
    ):
        self.key_template = key
        self.ttl = ttl
        self.lock_template = lock_key
        self.lock_ttl = lock_ttl
        self.enqueue = enqueue

    def key(self, **params) -> str:
        return self.key_template.format(**params)

    def lock_key(self, **params) -> str:
        return self.lock_template.format(**params)

    def get(self, **params):
        return cache_get(self.key(**params))

    def store(
        self, value, *, ttl: int | None = None, release=True, **params
    ) -> None:
        """Cache a freshly computed value and release the refresh lock.

        A pass that stores many values under one shared lock passes
        ``release=False`` and calls ``release()`` once at the end.
        """
        cache_set(self.key(**params), value, self.ttl if ttl is None else ttl)
        if release:
            self.release(**params)

    def release(self, **params) -> None:
        cache_delete(self.lock_key(**params))

    def get_or_queue(self, **params):
        """The cached value, or None after queueing one refresh."""
        key = self.key(**params)
        value = cache_get(key)
        if value is not None:
            return value
        if cache_add(self.lock_key(**params), True, self.lock_ttl):
            try:
                self.enqueue(**params)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Could not queue a refresh of %s", key)
                self.release(**params)
        # Eager Celery (tests) fills the cache during the call above.
        return cache_get(key)

    def get_or_compute(
        self,
        compute: Callable[[], Any],
        *,
        ttl: int | None = None,
        wait_seconds: float = 5.0,
        poll_seconds: float = 0.1,
        **params,
    ):
        """The cached value, computing and caching it on a miss."""
        key = self.key(**params)
        value = cache_get(key)
        if value is not None:
            return value
        lock = self.lock_key(**params)
        claimed = _cache_add(lock, True, self.lock_ttl)
        if claimed is _ERROR:
            # Cache down: nothing to wait for and nowhere to store it.
            return compute()
        if claimed:
            try:
                value = compute()
                cache_set(key, value, self.ttl if ttl is None else ttl)
                return value
            finally:
                cache_delete(lock)
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            time.sleep(poll_seconds)
            value = cache_get(key)
            if value is not None:
                return value
        return compute()
