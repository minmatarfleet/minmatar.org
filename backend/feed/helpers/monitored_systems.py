from __future__ import annotations

import threading
import time
from typing import Iterable

from feed.models import FeedMonitoredSystem

_cache_lock = threading.Lock()
_cached_ids: frozenset[int] | None = None
_cache_loaded_at: float = 0.0
CACHE_TTL_SECONDS = 300


def invalidate_monitored_systems_cache() -> None:
    global _cached_ids, _cache_loaded_at
    with _cache_lock:
        _cached_ids = None
        _cache_loaded_at = 0.0


def get_monitored_system_ids(*, force_refresh: bool = False) -> frozenset[int]:
    global _cached_ids, _cache_loaded_at
    now = time.monotonic()
    with _cache_lock:
        if (
            not force_refresh
            and _cached_ids is not None
            and (now - _cache_loaded_at) < CACHE_TTL_SECONDS
        ):
            return _cached_ids

    ids = frozenset(
        FeedMonitoredSystem.objects.filter(is_active=True).values_list(
            "solar_system_id", flat=True
        )
    )
    with _cache_lock:
        _cached_ids = ids
        _cache_loaded_at = now
    return ids


def is_monitored_system(
    solar_system_id: int, allowlist: Iterable[int] | None = None
) -> bool:
    if allowlist is not None:
        return solar_system_id in allowlist
    return solar_system_id in get_monitored_system_ids()
