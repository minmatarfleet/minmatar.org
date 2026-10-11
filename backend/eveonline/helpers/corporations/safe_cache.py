"""Cache access that degrades instead of failing the request.

Corporation pages treat the cache as an accelerator: if Redis is down they
render without cached stats rather than returning a 500.
"""

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)


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


def cache_add(key, value, timeout) -> bool:
    try:
        return cache.add(key, value, timeout)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Cache add failed for %s", key, exc_info=True)
        return False


def cache_delete(key) -> None:
    try:
        cache.delete(key)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Cache delete failed for %s", key, exc_info=True)
