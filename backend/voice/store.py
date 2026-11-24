"""The Redis keys the voice service reads, and a client for them.

``VOICE_REDIS_URL = "memory://"`` (the test settings) gives an in-process
store, so tests never need a Redis server.
"""

from __future__ import annotations

import fnmatch
import threading

from django.conf import settings

PREFIX = "voice:"
CHAR_KEY = PREFIX + "char:{}"  # character id -> record JSON
IDENTITY_KEY = PREFIX + "identity:{}"  # identity id -> character id
CERT_KEY = PREFIX + "cert:{}"  # certificate hash -> identity id
LEASES_KEY = PREFIX + "leases"  # branch -> lease JSON
META_KEY = PREFIX + "meta"  # {"count": n, "built_at": iso}
CHANGED_CHANNEL = PREFIX + "changed"  # pub/sub: character id or "leases"
COMMANDS_KEY = PREFIX + "commands"  # list of {"action": "kick", ...}
HEARTBEAT_KEY = PREFIX + "heartbeat"  # written by the voice service


class MemoryStore:
    """The few Redis calls the publisher makes, kept in a dict."""

    def __init__(self):
        self.data: dict[str, object] = {}
        self.published: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def get(self, key):
        value = self.data.get(key)
        return value.encode() if isinstance(value, str) else value

    def set(self, key, value, ex=None):  # pylint: disable=unused-argument
        with self._lock:
            self.data[key] = value if isinstance(value, str) else str(value)
        return True

    def delete(self, *keys):
        with self._lock:
            return sum(
                1 for key in keys if self.data.pop(key, None) is not None
            )

    def publish(self, channel, message):
        self.published.append((channel, str(message)))
        return 0

    def rpush(self, key, *values):
        with self._lock:
            items = self.data.setdefault(key, [])
            items.extend(str(v) for v in values)
            return len(items)

    def lrange(self, key, start, end):
        items = self.data.get(key) or []
        end = None if end == -1 else end + 1
        return [v.encode() for v in items[start:end]]

    def scan_iter(
        self, match="*", count=None
    ):  # pylint: disable=unused-argument
        for key in list(self.data):
            if fnmatch.fnmatch(key, match):
                yield key.encode()

    def flush(self):
        self.data.clear()
        self.published.clear()


_memory = MemoryStore()
_client = None


def get_client():
    """The Redis client for voice keys (a MemoryStore under tests)."""
    global _client  # pylint: disable=global-statement
    url = getattr(settings, "VOICE_REDIS_URL", "memory://")
    if url.startswith("memory://"):
        return _memory
    if _client is None:
        import redis  # pylint: disable=import-outside-toplevel

        _client = redis.Redis.from_url(url, socket_timeout=5)
    return _client


def memory_store() -> MemoryStore:
    return _memory
