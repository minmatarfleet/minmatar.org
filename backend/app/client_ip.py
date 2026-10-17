"""Client address for per-visitor limits and counts."""

from django.conf import settings
from django.http import HttpRequest


def trusted_proxy_count() -> int:
    return max(0, int(getattr(settings, "TRUSTED_PROXY_COUNT", 1)))


def client_ip(request: HttpRequest) -> str:
    """The address the outermost trusted proxy saw the request come from.

    Each trusted proxy appends the address it received the request from to
    X-Forwarded-For, so with N trusted hops the client is the Nth entry from
    the right. Entries further left came with the request and are not used.
    """
    remote_addr = request.META.get("REMOTE_ADDR") or "unknown"
    hops = trusted_proxy_count()
    if hops == 0:
        return remote_addr
    forwarded = [
        entry.strip()
        for entry in (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(
            ","
        )
        if entry.strip()
    ]
    if not forwarded:
        return remote_addr
    # Fewer entries than trusted hops: every entry was added by a trusted
    # proxy, and the left-most is the one closest to the client.
    return forwarded[-hops] if len(forwarded) >= hops else forwarded[0]
