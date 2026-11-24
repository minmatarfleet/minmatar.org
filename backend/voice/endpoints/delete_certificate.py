"""DELETE /api/voice/certificates/{id}: forget a Mumble certificate."""

from app.errors import ErrorResponse
from voice.endpoints.base import router
from voice.identity import VoiceAuth, request_identity
from voice.models import VoiceAuditEvent
from voice.publisher import (
    publish_character,
    queue_kick,
    unpublish_certificate,
)


@router.delete(
    "/certificates/{certificate_id}",
    summary="Revoke a Mumble certificate",
    auth=VoiceAuth(),
    response={204: None, 404: ErrorResponse},
)
def delete_certificate(request, certificate_id: int):
    identity = request_identity(request)
    cert = (
        identity.certificates.filter(id=certificate_id).first()
        if identity
        else None
    )
    if cert is None:
        return 404, ErrorResponse(detail="Certificate not found.")
    unpublish_certificate(cert.cert_hash)
    cert.delete()
    VoiceAuditEvent.record(
        VoiceAuditEvent.KIND_CERT_REVOKED, character_id=identity.character_id
    )
    publish_character(identity.character_id)
    queue_kick(identity.id, "This certificate was revoked on the website.")
    return 204, None
