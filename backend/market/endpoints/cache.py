"""Response caching for market API endpoints."""

import functools

from app.cache import CachedRollup

CACHE_PREFIX = "market:api"
DEFAULT_TIMEOUT = 300  # 5 minutes
# Long enough for the slowest market endpoint; waiters give up after 5s.
COMPUTE_LOCK_SECONDS = 60


def get_cached(key_suffix: str, timeout: int = DEFAULT_TIMEOUT):
    """
    Decorator that caches the view response by key_suffix.
    key_suffix can be a string or a callable(request, **kwargs) -> str.

    These are light queries, so a miss computes inline, one request at a
    time (the rest wait for its result). A cache outage computes without
    caching instead of failing the request.
    """
    responses = CachedRollup(
        key=CACHE_PREFIX + ":{suffix}",
        ttl=timeout,
        lock_key=CACHE_PREFIX + ":{suffix}:computing",
        lock_ttl=COMPUTE_LOCK_SECONDS,
    )

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            suffix = (
                key_suffix(request, *args, **kwargs)
                if callable(key_suffix)
                else key_suffix
            )
            return responses.get_or_compute(
                lambda: view_func(request, *args, **kwargs), suffix=suffix
            )

        return wrapper

    return decorator
