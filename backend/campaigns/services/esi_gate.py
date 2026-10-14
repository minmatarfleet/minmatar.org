"""A shared budget gate in front of ESI.

ESI enforces two independent limits: an app-wide error limit of 100 non-2xx
responses a minute, and a token bucket per group x application x character
over a 15-minute window. Nothing in the platform reads either header today,
so campaign polling keeps its own ledger in the cache and refuses to spend
the last of a budget.
"""

from __future__ import annotations

import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)

# ESI's own token budget per group x application x character over a rolling
# 15 minutes. A 2xx costs 2 tokens, a 3xx (a 304 from an ETag) costs 1 and a
# 4xx costs 5, so char-notification's 15 tokens is about seven full fetches.
GROUP_LIMITS = {
    "char-notification": 15,
    "char-killmail": 30,
    "killmail": 3600,
    "factional-warfare": 150,
    "fleet": 1800,
    "corp-project": 600,
    # No published bucket; bounded by the app-wide error limit only.
    "universe-names": 0,
}

WINDOW_SECONDS = 15 * 60
RESERVE_RATIO = 0.2
ERROR_BUDGET_FLOOR = 20
ERROR_BUDGET_KEY = "campaigns:esi:error_budget"
ERROR_BUDGET_RESET_KEY = "campaigns:esi:error_reset"


def _cache_get(key: str, default=None):
    """Read the ledger, tolerating a cache that is down.

    The gate is politeness on top of ESI's own limits, not a correctness
    requirement: ESI still answers 429 and 420 when we overstep. Losing Redis
    should degrade the budget tracking, not stop every campaign poller.
    """
    try:
        return cache.get(key, default)
    except Exception:  # pragma: no cover - depends on the cache backend
        logger.warning("ESI budget cache unavailable on read", exc_info=True)
        return default


def _cache_set(key: str, value, timeout: int) -> bool:
    try:
        cache.set(key, value, timeout)
        return True
    except Exception:  # pragma: no cover
        logger.warning("ESI budget cache unavailable on write", exc_info=True)
        return False


def _bucket_key(group: str, character_id: int | None) -> str:
    window = int(time.time() // WINDOW_SECONDS)
    return f"campaigns:esi:{group}:{character_id or 'public'}:{window}"


def spend(group: str, character_id: int | None = None, cost: int = 2) -> bool:
    """Record a call against a bucket. False once the reserve is reached."""
    limit = GROUP_LIMITS.get(group)
    if limit is None or _unbucketed(group):
        return True

    key = _bucket_key(group, character_id)
    try:
        cache.get_or_set(key, 0, WINDOW_SECONDS + 60)
        used = cache.incr(key, cost)
    except ValueError:
        # The key expired between get_or_set and incr.
        _cache_set(key, cost, WINDOW_SECONDS + 60)
        used = cost
    except Exception:  # pragma: no cover
        logger.warning("ESI budget cache unavailable on spend", exc_info=True)
        return True

    return used <= _spendable(limit)


def can_spend(group: str, character_id: int | None = None) -> bool:
    """True when this bucket and the app-wide error budget both have room."""
    if error_budget() < ERROR_BUDGET_FLOOR:
        logger.warning("ESI error budget low, holding %s calls", group)
        return False

    limit = GROUP_LIMITS.get(group)
    if limit is None or _unbucketed(group):
        return True
    used = _cache_get(_bucket_key(group, character_id), 0) or 0
    return used < _spendable(limit)


def _spendable(limit: int) -> int:
    """Tokens we are willing to use, keeping a fifth of the bucket in hand."""
    return int(limit * (1 - RESERVE_RATIO))


def _unbucketed(group: str) -> bool:
    """True for routes ESI does not put in a token bucket."""
    return GROUP_LIMITS.get(group) == 0


def error_budget() -> int:
    """Remaining app-wide error allowance this minute."""
    reset_at = _cache_get(ERROR_BUDGET_RESET_KEY)
    if reset_at is None or reset_at < time.time():
        _cache_set(ERROR_BUDGET_KEY, 100, 120)
        _cache_set(ERROR_BUDGET_RESET_KEY, time.time() + 60, 120)
        return 100
    budget = _cache_get(ERROR_BUDGET_KEY, 100)
    return 100 if budget is None else budget


def record_error(retry_after: int | None = None) -> None:
    """Count a non-2xx response against the app-wide error limit."""
    try:
        cache.decr(ERROR_BUDGET_KEY, 1)
    except ValueError:
        _cache_set(ERROR_BUDGET_KEY, 99, 120)
    except Exception:  # pragma: no cover
        logger.warning("ESI budget cache unavailable on error", exc_info=True)
    if retry_after:
        _cache_set(ERROR_BUDGET_RESET_KEY, time.time() + retry_after, 300)


def observe_headers(headers: dict) -> None:
    """Believe ESI's own numbers over our ledger when they are present."""
    if not headers:
        return
    remaining = headers.get("X-Esi-Error-Limit-Remain")
    if remaining is not None:
        try:
            # Record the window too, or the next read would treat the number
            # as expired and reset it straight back to a full budget.
            reset_in = int(headers.get("X-Esi-Error-Limit-Reset") or 60)
            _cache_set(ERROR_BUDGET_KEY, int(remaining), reset_in + 60)
            _cache_set(
                ERROR_BUDGET_RESET_KEY, time.time() + reset_in, reset_in + 60
            )
        except (TypeError, ValueError):
            pass
    group = headers.get("X-Ratelimit-Group")
    used = headers.get("X-Ratelimit-Used")
    if group and used is not None:
        try:
            _cache_set(f"campaigns:esi:observed:{group}", int(used), 900)
        except (TypeError, ValueError):
            pass


def snapshot() -> dict:
    """What the KPI panel shows for ESI health."""
    return {
        "error_budget": error_budget(),
        "groups": {
            group: _cache_get(f"campaigns:esi:observed:{group}")
            for group in GROUP_LIMITS
        },
    }
