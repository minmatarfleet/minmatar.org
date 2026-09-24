"""Rate limits for inferred-sales volume pagination."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest

from notifications.rate_limit import acquire

# Anonymous: a handful of page/filter flips, then ask them to log in.
# Capacity 8 ≈ first page SSR + a few chip/sort/next clicks.
ANON_RATE = 3 / 60
ANON_CAPACITY = 8.0
# Logged-in members get more headroom (~40/min).
USER_RATE = 40 / 60
USER_CAPACITY = 20.0


class VolumeRateLimited(Exception):
    def __init__(self, retry_after: float, *, login_suggested: bool = False):
        self.retry_after = max(1.0, float(retry_after))
        self.login_suggested = login_suggested
        super().__init__(f"rate_limited retry_after={self.retry_after:.0f}")


def client_ip(request: HttpRequest) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    cf = request.META.get("HTTP_CF_CONNECTING_IP") or ""
    if cf:
        return cf.strip()
    return request.META.get("REMOTE_ADDR") or "unknown"


def _auth_user(request: HttpRequest):
    auth = getattr(request, "auth", None)
    if auth is not None and not isinstance(auth, AnonymousUser):
        return auth
    user = getattr(request, "user", None)
    if (
        user is not None
        and not isinstance(user, AnonymousUser)
        and getattr(user, "is_authenticated", False)
    ):
        return user
    return None


def enforce_volume_rate_limit(request: HttpRequest) -> None:
    """Raise VolumeRateLimited when the caller bucket is empty."""
    user = _auth_user(request)
    if user is None:
        ip = client_ip(request)
        allowed, retry = acquire(
            f"market:volume:anon:{ip}",
            rate_per_second=ANON_RATE,
            capacity=ANON_CAPACITY,
        )
        if not allowed:
            raise VolumeRateLimited(retry, login_suggested=True)
        return

    allowed, retry = acquire(
        f"market:volume:user:{user.id}",
        rate_per_second=USER_RATE,
        capacity=USER_CAPACITY,
    )
    if not allowed:
        raise VolumeRateLimited(retry)
