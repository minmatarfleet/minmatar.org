"""Response caching for market API endpoints."""

import functools

from django.core.cache import cache

CACHE_PREFIX = "market:api"
DEFAULT_TIMEOUT = 300  # 5 minutes


def get_cached(key_suffix: str, timeout: int = DEFAULT_TIMEOUT):
    """
    Decorator that caches the view response by key_suffix.
    key_suffix can be a string or a callable(request, **kwargs) -> str.
    """

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            suffix = (
                key_suffix(request, *args, **kwargs)
                if callable(key_suffix)
                else key_suffix
            )
            key = f"{CACHE_PREFIX}:{suffix}"
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = view_func(request, *args, **kwargs)
            cache.set(key, result, timeout=timeout)
            return result

        return wrapper

    return decorator
