"""Celery Once backend compatible with Django's LocMemCache."""

from __future__ import annotations

from celery_once import AlreadyQueued
from django.core.cache import cache


class DjangoBackend:
    """Lock via Django cache; tolerates backends without ``ttl`` (e.g. LocMem)."""

    def __init__(self, settings):
        del settings

    @staticmethod
    def raise_or_lock(key, timeout):
        acquired = cache.add(key=key, value="lock", timeout=timeout)
        if acquired:
            return

        remaining = timeout
        ttl = getattr(cache, "ttl", None)
        if callable(ttl):
            try:
                remaining = int(ttl(key))
            except (TypeError, ValueError):
                remaining = timeout
        raise AlreadyQueued(remaining)

    @staticmethod
    def clear_lock(key):
        return cache.delete(key)
