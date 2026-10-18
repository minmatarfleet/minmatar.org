"""Which app versions call the API.

The desktop app sends ``X-Minmatar-Client: desktop/<version> (<installer|
portable>)`` on every request. Portable builds never update themselves, so
before a field the desktop reads is renamed or removed, someone has to be able
to ask "does any version that reads it still call us?". This records the
answer cheaply: a Sentry tag on the request, a per-day counter in the cache,
and one log line the first time each version shows up in a day.

Browsers never send the header (it is not in the CORS allow-list), and a
request without it, or with a value that doesn't parse, is left alone.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

import sentry_sdk
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

HEADER = "X-Minmatar-Client"
# desktop/0.10.0 (installer). The pattern bounds what we count, so a junk
# header can't create unbounded cache keys.
CLIENT_PATTERN = re.compile(
    r"^(?P<app>desktop)/(?P<version>\d{1,4}\.\d{1,4}\.\d{1,4})"
    r"(?: \((?P<build>installer|portable)\))?$"
)
KEEP_DAYS = 35
COUNT_KEY = "clients:{day}:{client}"
SEEN_KEY = "clients:{day}:seen"


def parse_client(value: str | None) -> str | None:
    """The normalised ``app/version (build)`` string, or None."""
    if not value:
        return None
    match = CLIENT_PATTERN.match(value.strip())
    if not match:
        return None
    build = match["build"] or "unknown"
    return f"{match['app']}/{match['version']} ({build})"


def record(client: str, day: date | None = None) -> None:
    day = day or timezone.now().date()
    ttl = KEEP_DAYS * 86400
    key = COUNT_KEY.format(day=day.isoformat(), client=client)
    if cache.add(key, 1, ttl):
        # First request from this version today: remember it so the counts
        # can be listed, and say so once in the log.
        seen_key = SEEN_KEY.format(day=day.isoformat())
        seen = cache.get(seen_key) or []
        if client not in seen:
            cache.set(seen_key, [*seen, client], ttl)
        logger.info("api client seen today: %s", client)
        return
    try:
        cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.add(key, 1, ttl)


def counts(days: int = 7, today: date | None = None) -> dict[str, dict]:
    """{day: {client: requests}} for the last ``days`` days, newest first."""
    today = today or timezone.now().date()
    result = {}
    for back in range(days):
        day = (today - timedelta(days=back)).isoformat()
        seen = cache.get(SEEN_KEY.format(day=day)) or []
        result[day] = {
            client: cache.get(COUNT_KEY.format(day=day, client=client)) or 0
            for client in seen
        }
    return result


class ClientVersionMiddleware:
    """Tag and count requests that name their client. Never fails one."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        client = parse_client(request.headers.get(HEADER))
        if client:
            try:
                sentry_sdk.set_tag("client", client)
                record(client)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.warning("Could not record api client", exc_info=True)
        return self.get_response(request)
