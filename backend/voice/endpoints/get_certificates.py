"""GET /api/voice/certificates: the Mumble certificates bound to a character."""

from app.errors import ErrorResponse
from voice.endpoints.base import router
from voice.endpoints.schemas import VoiceCertificateResponse
from voice.identity import VoiceAuth, request_identity


@router.get(
    "/certificates",
    summary="Mumble certificates bound to the character",
    auth=VoiceAuth(),
    response={200: list[VoiceCertificateResponse], 404: ErrorResponse},
)
def get_certificates(request):
    identity = request_identity(request)
    if identity is None:
        return 404, ErrorResponse(detail="No character.")
    return [
        VoiceCertificateResponse(
            id=cert.id,
            fingerprint=cert.cert_hash[:12],
            created_at=cert.created_at,
            last_used_at=cert.last_used_at,
        )
        for cert in identity.certificates.order_by("-created_at")
    ]
