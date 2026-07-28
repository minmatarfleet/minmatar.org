"""Cluster-safe Redis token-bucket rate limiting for notification channels."""

from __future__ import annotations

import time

from django.core.cache import cache

# Lua: token bucket. KEYS[1]=bucket key; ARGV=rate, capacity, now, requested
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  ts = now
end
local delta = math.max(0, now - ts)
tokens = math.min(capacity, tokens + delta * rate)
local allowed = 0
local retry_after = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
else
  retry_after = (requested - tokens) / rate
end
redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, math.ceil(capacity / rate) + 5)
return {allowed, retry_after, tokens}
"""


def acquire(
    bucket: str,
    *,
    rate_per_second: float,
    capacity: float | None = None,
    tokens: float = 1.0,
) -> tuple[bool, float]:
    """
    Try to take `tokens` from a Redis token bucket.

    Returns (allowed, retry_after_seconds).
    Falls back to allowing the call if Redis/Lua is unavailable (locmem tests).
    """
    if rate_per_second <= 0:
        return True, 0.0
    cap = capacity if capacity is not None else max(rate_per_second, tokens)
    key = f"notifications:ratelimit:{bucket}"
    now = time.time()
    client = getattr(cache, "client", None)
    if client is None:
        # LocMemCache (tests): coarse per-key throttle.
        return _locmem_acquire(key, rate_per_second, cap, tokens, now)
    try:
        redis = client.get_client(write=True)
        result = redis.eval(
            _TOKEN_BUCKET_LUA,
            1,
            key,
            rate_per_second,
            cap,
            now,
            tokens,
        )
        allowed = bool(int(result[0]))
        retry_after = float(result[1] or 0)
        return allowed, retry_after
    except Exception:
        return _locmem_acquire(key, rate_per_second, cap, tokens, now)


def _locmem_acquire(key, rate, capacity, requested, now) -> tuple[bool, float]:
    data = cache.get(key) or {"tokens": capacity, "ts": now}
    tokens = float(data["tokens"])
    ts = float(data["ts"])
    tokens = min(capacity, tokens + max(0.0, now - ts) * rate)
    if tokens >= requested:
        tokens -= requested
        cache.set(key, {"tokens": tokens, "ts": now}, timeout=60)
        return True, 0.0
    retry_after = (requested - tokens) / rate if rate else 1.0
    cache.set(key, {"tokens": tokens, "ts": now}, timeout=60)
    return False, retry_after
