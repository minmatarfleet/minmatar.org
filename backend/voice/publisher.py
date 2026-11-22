"""Publish voice records and leases to Redis for the voice service.

Only characters with a ``VoiceIdentity`` (signed in on /voice) get a record:
the identity id is their Mumble user id. Every write announces the change on
``voice:changed`` so the voice service reconciles at once instead of waiting
for its next tick.
"""

from __future__ import annotations

import json
import logging

from django.utils import timezone

from voice import store
from voice.access import voice_record
from voice.models import VoiceCertificate, VoiceChannelLease, VoiceIdentity

logger = logging.getLogger(__name__)


def _dump(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def publish_character(character_id: int, client=None) -> dict | None:
    """Write one character's record. Returns it, or None without an identity."""
    client = client or store.get_client()
    identity = VoiceIdentity.objects.filter(character_id=character_id).first()
    if identity is None:
        client.delete(store.CHAR_KEY.format(int(character_id)))
        return None
    record = voice_record(character_id).to_json()
    client.set(store.CHAR_KEY.format(identity.character_id), _dump(record))
    client.set(
        store.IDENTITY_KEY.format(identity.id), str(identity.character_id)
    )
    for cert_hash in identity.certificates.values_list("cert_hash", flat=True):
        if cert_hash:
            client.set(store.CERT_KEY.format(cert_hash), str(identity.id))
    client.publish(store.CHANGED_CHANNEL, str(identity.character_id))
    return record


def publish_characters(character_ids, client=None) -> int:
    client = client or store.get_client()
    count = 0
    for character_id in set(int(c) for c in character_ids):
        if publish_character(character_id, client=client) is not None:
            count += 1
    return count


def unpublish_certificate(cert_hash: str, client=None) -> None:
    if not cert_hash:
        return
    client = client or store.get_client()
    client.delete(store.CERT_KEY.format(cert_hash))


def leases_payload() -> dict:
    return {
        str(lease.branch): {
            "lease_id": lease.id,
            "fleet_id": lease.fleet_id,
            "wing_channels": lease.wing_channels or {},
        }
        for lease in VoiceChannelLease.active().order_by("branch")
    }


def publish_leases(client=None) -> dict:
    client = client or store.get_client()
    payload = leases_payload()
    client.set(store.LEASES_KEY, _dump(payload))
    client.publish(store.CHANGED_CHANNEL, "leases")
    return payload


def queue_kick(identity_id: int, message: str, client=None) -> None:
    """Ask the voice service to drop a connected pilot."""
    client = client or store.get_client()
    client.rpush(
        store.COMMANDS_KEY,
        _dump(
            {
                "action": "kick",
                "identity_id": int(identity_id),
                "message": message,
            }
        ),
    )
    client.publish(store.CHANGED_CHANNEL, "commands")


def rebuild_all(client=None) -> int:
    """Republish every identity, every certificate and the leases.

    Runs when ``voice:meta`` shows fewer records than identities (Redis lost
    its data) and from ``manage.py voice_status --rebuild``.
    """
    client = client or store.get_client()
    known = set(VoiceCertificate.objects.values_list("cert_hash", flat=True))
    for key in client.scan_iter(match=store.CERT_KEY.format("*")):
        cert_hash = key.decode().split(":", 2)[-1]
        if cert_hash not in known:
            client.delete(key.decode())
    count = publish_characters(
        VoiceIdentity.objects.values_list("character_id", flat=True),
        client=client,
    )
    publish_leases(client=client)
    client.set(
        store.META_KEY,
        _dump({"count": count, "built_at": timezone.now().isoformat()}),
    )
    return count


def records_missing(client=None) -> bool:
    """True when Redis holds fewer records than there are identities.

    Redis lost its data (restart without persistence, flush): rebuild.
    """
    client = client or store.get_client()
    if client.get(store.LEASES_KEY) is None:
        return True
    published = sum(
        1 for _ in client.scan_iter(match=store.CHAR_KEY.format("*"))
    )
    return published < VoiceIdentity.objects.count()
