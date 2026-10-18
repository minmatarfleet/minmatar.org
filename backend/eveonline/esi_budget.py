"""A shared budget gate in front of ESI.

ESI enforces two independent limits: an app-wide error limit of 100 non-2xx
responses a minute, and a token bucket per group x application x character
over a 15-minute window. Campaign polls and the structure notification
poller share this cache ledger and refuse to spend the last of a budget.
Every raw ESI call (``eveonline.esi_http``) reports its errors here too, so
the app-wide error budget sees the whole application.

Moved from ``campaigns.services.esi_gate``, which remains an alias. The cache
keys keep their ``campaigns:esi:`` prefix so a deploy does not reset them.
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
# Same floor the structure poller uses when Retry-After is missing or tiny.
DEFAULT_RETRY_AFTER_SECONDS = 120
MIN_RETRY_AFTER_SECONDS = 30
ETAG_TTL_SECONDS = 60 * 60


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


def token_cost(status: int) -> int:
    """ESI token cost for one response. 5xx is free; a 4xx is expensive."""
    if 200 <= status < 300:
        return 2
    if 300 <= status < 400:
        return 1
    if 400 <= status < 500:
        return 5
    return 0


def _pause_key(group: str | None, character_id: int | None) -> str:
    if group is None:
        return "campaigns:esi:paused:all"
    return f"campaigns:esi:paused:{group}:{character_id or 'public'}"


def pause(group: str | None, character_id: int | None, seconds: int) -> None:
    """Hold this bucket, or every bucket when ``group`` is None."""
    seconds = max(int(seconds), 1)
    _cache_set(_pause_key(group, character_id), time.time() + seconds, seconds)


def pause_remaining(
    group: str | None = None, character_id: int | None = None
) -> int:
    """Seconds left on a pause, including an app-wide 420 hold."""
    keys = [_pause_key(None, None)]
    if group is not None:
        keys.append(_pause_key(group, character_id))
    now = time.time()
    remaining = 0
    for key in keys:
        until = _cache_get(key)
        if until is None:
            continue
        try:
            remaining = max(remaining, int(until - now))
        except (TypeError, ValueError):
            continue
    return max(remaining, 0)


def _retry_after_seconds(headers: dict) -> int:
    raw = headers.get("Retry-After")
    if raw is not None:
        try:
            return max(int(raw), MIN_RETRY_AFTER_SECONDS)
        except (TypeError, ValueError):
            pass
    return DEFAULT_RETRY_AFTER_SECONDS


def _etag_key(character_id: int) -> str:
    return f"campaigns:esi:etag:char-notification:{character_id}"


def notification_etag(character_id: int) -> str | None:
    """Last ETag ESI gave us for this character's notifications."""
    return _cache_get(_etag_key(character_id))


def remember_notification_etag(character_id: int, etag: str) -> None:
    _cache_set(_etag_key(character_id), etag, ETAG_TTL_SECONDS)


def note_call(
    group: str,
    character_id: int | None,
    status: int,
    headers: dict | None = None,
) -> None:
    """Record one finished ESI call: cost, error budget, pause, and ETag.

    A 429 pauses only that group and character. A 420 pauses every group
    for ESI's reset window. Neither one rewrites the app-wide error-budget
    clock, so one character's Retry-After cannot refill everyone else's
    allowance.
    """
    headers = headers or {}
    observe_response(status, headers)
    cost = token_cost(status)
    if cost:
        spend(group, character_id, cost)
    if status == 429:
        seconds = _retry_after_seconds(headers)
        pause(group, character_id, seconds)
        logger.warning(
            "ESI %s paused for character %s (%ss) after HTTP 429",
            group,
            character_id,
            seconds,
        )
    if group == "char-notification" and character_id is not None:
        etag = headers.get("ETag")
        if etag:
            remember_notification_etag(character_id, str(etag))


def observe_response(status: int, headers: dict | None = None) -> None:
    """Account one ESI response against the app-wide error budget.

    The group-free half of ``note_call``: believe ESI's error-limit headers,
    count an error the headers did not already count, and hold every group
    on a 420. Raw ESI calls with no token bucket of their own use this.
    """
    headers = headers or {}
    has_remain = headers.get("X-Esi-Error-Limit-Remain") is not None
    observe_headers(headers)
    # ESI's remain header already counts this response. Decrementing again
    # would spend the error budget twice.
    if status >= 400 and not has_remain:
        record_error()
    if status == 420:
        try:
            seconds = int(headers.get("X-Esi-Error-Limit-Reset") or 60)
        except (TypeError, ValueError):
            seconds = 60
        seconds = max(seconds, MIN_RETRY_AFTER_SECONDS)
        pause(None, None, seconds)
        logger.warning(
            "ESI error-limited, pausing every group for %ss", seconds
        )


def note_response(group: str, character_id: int | None, response) -> None:
    """Account for an ``EsiResponse``. Local token errors are not ESI calls."""
    status = getattr(response, "response_code", None)
    http = getattr(response, "response", None)
    headers = getattr(http, "headers", None) if http is not None else None
    if isinstance(status, int) and 100 <= status < 600:
        note_call(
            group,
            character_id,
            status,
            dict(headers) if headers else {},
        )
        return
    if hasattr(response, "success") and not response.success():
        record_error()


def can_spend(group: str, character_id: int | None = None) -> bool:
    """True when this bucket and the app-wide error budget both have room."""
    if pause_remaining(group, character_id) > 0:
        return False
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


def record_error() -> None:
    """Count a non-2xx response against the app-wide error limit.

    A Retry-After belongs on ``pause``, not here. Sliding this reset clock
    would treat one character's 429 as a fresh error budget for the app.
    """
    try:
        cache.decr(ERROR_BUDGET_KEY, 1)
    except ValueError:
        _cache_set(ERROR_BUDGET_KEY, 99, 120)
        # Open the window too, or the next read would see no reset time,
        # refill the budget to 100 and forget this error.
        if _cache_get(ERROR_BUDGET_RESET_KEY) is None:
            _cache_set(ERROR_BUDGET_RESET_KEY, time.time() + 60, 120)
    except Exception:  # pragma: no cover
        logger.warning("ESI budget cache unavailable on error", exc_info=True)


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
