"""POST /api/voice/internal/lookup: a record the voice service missed."""

from voice.connect import identity_for_certificate
from voice.endpoints.base import router
from voice.endpoints.internal_auth import InternalSecret, record_for
from voice.endpoints.schemas import VoiceInternalLookupRequest
from voice.models import VoiceIdentity


@router.post(
    "/internal/lookup",
    auth=InternalSecret(),
    include_in_schema=False,
    response={200: dict, 404: dict},
)
def post_internal_lookup(request, payload: VoiceInternalLookupRequest):
    """A record the voice service missed in Redis: republish and return it."""
    identity = None
    if payload.cert_hash:
        identity = identity_for_certificate(payload.cert_hash)
    elif payload.identity_id:
        identity = VoiceIdentity.objects.filter(id=payload.identity_id).first()
    elif payload.character_id:
        identity = VoiceIdentity.objects.filter(
            character_id=payload.character_id
        ).first()
    return record_for(identity)
