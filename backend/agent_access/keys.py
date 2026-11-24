"""Creating and checking agent keys."""

import hashlib
import logging
import secrets

from django.core.cache import cache
from django.utils import timezone

from app.client_ip import client_ip as shared_client_ip

from .models import AgentKey

logger = logging.getLogger(__name__)

KEY_PREFIX = "mfa_"
LAST_USED_WRITE_SECONDS = 60
FAILED_ALERT_SECONDS = 3600


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def assign_new_key(key: AgentKey) -> str:
    """Give an unsaved key a fresh secret; returns the raw value.

    The raw value is not stored anywhere: show it once, then drop it.
    """
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    key.key_prefix = raw[:12]
    key.key_hash = hash_key(raw)
    return raw


def create_key(name: str, created_by=None, **fields) -> tuple[AgentKey, str]:
    """A new saved key and its raw value."""
    key = AgentKey(name=name, created_by=created_by, **fields)
    raw = assign_new_key(key)
    key.save()
    return key, raw


def bearer_token(request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def client_ip(request) -> str | None:
    ip = shared_client_ip(request)
    return None if ip == "unknown" else ip


def authenticate(request) -> AgentKey | None:
    """The active key the request carries, or None."""
    raw = bearer_token(request)
    key = None
    if raw.startswith(KEY_PREFIX):
        key = AgentKey.objects.filter(key_hash=hash_key(raw)).first()
    if key is None or not key.is_active:
        if raw.startswith(KEY_PREFIX):
            # Someone holds a real-looking key; a bare scan is not alerted.
            _alert_failed(request, key)
        return None
    _note_used(key, client_ip(request))
    return key


def _alert_failed(request, key: AgentKey | None) -> None:
    """A refused key reaches Sentry, once an hour per address."""
    ip = client_ip(request) or "unknown"
    try:
        first = cache.add(f"agent_access:failed:{ip}", 1, FAILED_ALERT_SECONDS)
    except Exception:  # pylint: disable=broad-except
        # expected: cache down; alert anyway
        first = True
    if not first:
        return
    reason = "unknown key" if key is None else "revoked or expired key"
    logger.error(
        "Agent Discord endpoint refused a request (%s) from %s, key %s",
        reason,
        ip,
        key.key_prefix if key else "-",
    )


def _note_used(key: AgentKey, ip: str | None) -> None:
    now = timezone.now()
    stale = (
        key.last_used_at is None
        or (now - key.last_used_at).total_seconds() > LAST_USED_WRITE_SECONDS
    )
    if not stale and key.last_used_ip == ip:
        return
    if key.last_used_ip and ip and key.last_used_ip != ip:
        logger.info(
            "Agent key %s used from a new address %s (was %s)",
            key.key_prefix,
            ip,
            key.last_used_ip,
        )
    AgentKey.objects.filter(pk=key.pk).update(
        last_used_at=now, last_used_ip=ip
    )
    key.last_used_at = now
    key.last_used_ip = ip
