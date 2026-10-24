"""Moved to ``app.cache``; kept so existing imports keep working."""

from app.cache import (  # noqa: F401  pylint: disable=unused-import
    cache_add,
    cache_delete,
    cache_get,
    cache_set,
)
