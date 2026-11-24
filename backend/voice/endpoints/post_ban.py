"""POST /api/voice/bans: ban a character from voice."""

from app.errors import ErrorResponse
from eveonline.models import EveCharacter
from voice.endpoints.base import router
from voice.endpoints.fleet_helpers import AUTH
from voice.endpoints.schemas import VoiceBanRequest, VoiceBanResponse
from voice.identity import revoke_identity_access
from voice.models import VoiceAuditEvent, VoiceBan, VoiceIdentity
from voice.permissions import is_voice_admin
from voice.publisher import publish_character, queue_kick


@router.post(
    "/bans",
    summary="Ban a character from fleet voice",
    auth=AUTH,
    response={201: VoiceBanResponse, 403: ErrorResponse},
)
def post_ban(request, payload: VoiceBanRequest):
    if not is_voice_admin(request.user):
        return 403, ErrorResponse(detail="Voice admins only.")
    identity = VoiceIdentity.objects.filter(
        character_id=payload.character_id
    ).first()
    name = EveCharacter.objects.filter(
        character_id=payload.character_id
    ).values_list("character_name", flat=True).first() or (
        identity.character_name if identity else ""
    )
    ban = VoiceBan.objects.create(
        character_id=payload.character_id,
        character_name=name,
        reason=payload.reason,
        expires_at=payload.expires_at,
        created_by=request.user,
    )
    VoiceAuditEvent.record(
        VoiceAuditEvent.KIND_BAN,
        character_id=payload.character_id,
        actor=request.user,
        reason=payload.reason,
    )
    if identity:
        revoke_identity_access(identity)
        publish_character(identity.character_id)
        queue_kick(identity.id, "Banned from fleet voice.")
    return 201, VoiceBanResponse(
        id=ban.id,
        character_id=ban.character_id,
        character_name=ban.character_name,
        reason=ban.reason,
        expires_at=ban.expires_at,
    )
