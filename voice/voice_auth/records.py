"""Access records published by Django (backend/voice/publisher.py).

Reads Redis first. On a miss it asks Django's internal endpoint, which
republishes the record. If both fail, the caller answers "try again later"
rather than refusing a pilot who may well have access.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

CHAR_KEY = "voice:char:{}"
IDENTITY_KEY = "voice:identity:{}"
CERT_KEY = "voice:cert:{}"
LEASES_KEY = "voice:leases"
CHANGED_CHANNEL = "voice:changed"
COMMANDS_KEY = "voice:commands"
HEARTBEAT_KEY = "voice:heartbeat"
SUPPORTED_VERSION = 1


class Unavailable(Exception):
    """Neither Redis nor Django could answer."""


def _text(value):
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else str(value)


class RecordStore:
    def __init__(self, redis, internal=None):
        self.redis = redis
        self.internal = internal

    def _record(self, character_id):
        raw = _text(self.redis.get(CHAR_KEY.format(character_id)))
        if raw is None:
            return None
        record = json.loads(raw)
        if int(record.get("version", 0)) > SUPPORTED_VERSION:
            logger.warning("Voice record version %s is newer", record["version"])
        return record

    def _lookup(self, **query):
        if self.internal is None:
            raise Unavailable("no internal endpoint")
        return self.internal.lookup(**query)

    def by_identity(self, identity_id: int, *, fallback=True):
        try:
            character_id = _text(self.redis.get(IDENTITY_KEY.format(identity_id)))
            record = self._record(character_id) if character_id else None
        except Exception as exc:  # redis down
            if not fallback:
                raise Unavailable(str(exc)) from exc
            record = None
        if record is not None or not fallback:
            return record
        return self._lookup(identity_id=identity_id)

    def by_certificate(self, cert_hash: str):
        """The record bound to this certificate, None if unbound.

        An empty hash (a client without a certificate) never matches.
        """
        if not cert_hash:
            return None
        try:
            identity_id = _text(self.redis.get(CERT_KEY.format(cert_hash)))
        except Exception:  # redis down: ask Django
            identity_id = None
            return self._lookup(cert_hash=cert_hash)
        if identity_id is None:
            return self._lookup(cert_hash=cert_hash)
        return self.by_identity(int(identity_id))

    def redeem(self, password: str, cert_hash: str):
        if self.internal is None:
            raise Unavailable("no internal endpoint")
        return self.internal.redeem(password=password, cert_hash=cert_hash)

    def leases(self) -> dict:
        raw = _text(self.redis.get(LEASES_KEY))
        return json.loads(raw) if raw else {}

    def pop_commands(self) -> list[dict]:
        commands = []
        while True:
            raw = _text(self.redis.lpop(COMMANDS_KEY))
            if raw is None:
                return commands
            try:
                commands.append(json.loads(raw))
            except ValueError:
                logger.warning("Ignoring an unreadable voice command")


class InternalClient:
    """Django's /api/voice/internal/ endpoints, through the edge."""

    def __init__(self, base_url: str, secret: str, session=None, timeout=3):
        import requests  # pylint: disable=import-outside-toplevel

        self.base_url = base_url.rstrip("/")
        self.headers = {"X-Voice-Secret": secret}
        self.session = session or requests.Session()
        self.timeout = timeout

    def _post(self, path, body):
        try:
            response = self.session.post(
                f"{self.base_url}/{path}",
                json=body,
                headers=self.headers,
                timeout=self.timeout,
            )
        except Exception as exc:
            raise Unavailable(str(exc)) from exc
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise Unavailable(f"internal endpoint answered {response.status_code}")
        return response.json()

    def lookup(self, **query):
        return self._post("lookup", {k: v for k, v in query.items() if v})

    def redeem(self, password, cert_hash):
        return self._post("redeem", {"password": password, "cert_hash": cert_hash})
