"""Connect tokens and certificate binding.

**Connect** mints a one-time token (stored hashed, 2 minute expiry, bound to
the identity) inside a ``mumble://`` link. The first login with it binds the
client's certificate hash; later logins use the certificate. An empty hash
(a client without a certificate) is never bound or matched.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from voice.models import (
    MAX_CERTIFICATES,
    VoiceAuditEvent,
    VoiceCertificate,
    VoiceConnectToken,
    VoiceIdentity,
)

TOKEN_TTL = timedelta(minutes=2)
SERVER_TITLE = "Minmatar Fleet"
CLIENT_VERSION = "1.2.0"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mint_token(identity: VoiceIdentity) -> str:
    token = secrets.token_urlsafe(24)
    VoiceConnectToken.objects.create(
        identity=identity,
        token_hash=hash_token(token),
        expires_at=timezone.now() + TOKEN_TTL,
    )
    VoiceAuditEvent.record(
        VoiceAuditEvent.KIND_CONNECT_TOKEN, character_id=identity.character_id
    )
    return token


def mumble_url(identity: VoiceIdentity, token: str) -> str:
    name = quote(identity.character_name, safe="")
    secret = quote(token, safe="")
    host = settings.VOICE_HOST
    port = int(settings.VOICE_PORT)
    return (
        f"mumble://{name}:{secret}@{host}:{port}/"
        f"?title={quote(SERVER_TITLE)}&version={CLIENT_VERSION}"
    )


def redeem_token(token: str, cert_hash: str = "") -> VoiceIdentity | None:
    """Spend a connect token; bind the certificate when there is one.

    Returns the identity, or None for an unknown, spent or expired token,
    or a certificate bound to someone else. A certificate bound to another
    character on the same account (the pilot's old main) moves over.
    """
    if not token:
        return None
    now = timezone.now()
    with transaction.atomic():
        row = (
            VoiceConnectToken.objects.select_for_update()
            .filter(token_hash=hash_token(token), used_at__isnull=True)
            .select_related("identity")
            .first()
        )
        if row is None or row.expires_at <= now:
            return None
        if cert_hash and not _release_certificate(row.identity, cert_hash):
            return None
        row.used_at = now
        row.save(update_fields=["used_at"])
        if cert_hash:
            bind_certificate(row.identity, cert_hash)
        return row.identity


def _release_certificate(identity: VoiceIdentity, cert_hash: str) -> bool:
    """Free a certificate bound to another identity, so this one can bind it.

    Allowed only when both characters are on the same site account: the
    pilot changed their main and connects with the same Mumble client.
    Returns False when it belongs to someone else.
    """
    # pylint: disable=import-outside-toplevel
    from voice.access import owner_user_id
    from voice.publisher import unpublish_certificate

    others = list(
        VoiceCertificate.objects.filter(cert_hash=cert_hash)
        .exclude(identity=identity)
        .select_related("identity")
    )
    if not others:
        return True
    owner = owner_user_id(identity.character_id)
    if owner is None or any(
        owner_user_id(cert.identity.character_id) != owner for cert in others
    ):
        return False
    unpublish_certificate(cert_hash)
    for cert in others:
        VoiceAuditEvent.record(
            VoiceAuditEvent.KIND_CERT_REVOKED,
            character_id=cert.identity.character_id,
        )
        cert.delete()
    return True


def bind_certificate(
    identity: VoiceIdentity, cert_hash: str
) -> VoiceCertificate | None:
    """Bind a certificate, replacing the least recently used beyond three."""
    if not cert_hash:
        return None
    cert, created = VoiceCertificate.objects.get_or_create(
        identity=identity,
        cert_hash=cert_hash,
        defaults={"last_used_at": timezone.now()},
    )
    if not created:
        return cert
    VoiceAuditEvent.record(
        VoiceAuditEvent.KIND_CERT_BOUND, character_id=identity.character_id
    )
    extra = list(
        identity.certificates.order_by("-last_used_at", "-created_at")[
            MAX_CERTIFICATES:
        ]
    )
    if extra:
        # pylint: disable=import-outside-toplevel
        from voice.publisher import unpublish_certificate

        for old in extra:
            unpublish_certificate(old.cert_hash)
            old.delete()
    return cert


def identity_for_certificate(cert_hash: str) -> VoiceIdentity | None:
    if not cert_hash:
        return None
    cert = (
        VoiceCertificate.objects.filter(cert_hash=cert_hash)
        .select_related("identity")
        .first()
    )
    if cert is None:
        return None
    VoiceCertificate.objects.filter(pk=cert.pk).update(
        last_used_at=timezone.now()
    )
    return cert.identity
