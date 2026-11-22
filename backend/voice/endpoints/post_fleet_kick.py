"""POST /api/voice/fleets/{fleet_id}/kick: drop a pilot from the fleet's voice."""

from django.utils import timezone

from app.errors import ErrorResponse
from voice.endpoints.base import router
from voice.endpoints.fleet_helpers import AUTH, managed_fleet
from voice.endpoints.schemas import VoiceKickRequest
from voice.models import VoiceAuditEvent, VoiceGrant, VoiceIdentity
from voice.publisher import publish_character, queue_kick


@router.post(
    "/fleets/{fleet_id}/kick",
    summary="Kick a pilot and end their access to this fleet",
    auth=AUTH,
    response={204: None, 403: ErrorResponse, 404: ErrorResponse},
)
def post_fleet_kick(request, fleet_id: int, payload: VoiceKickRequest):
    fleet, error = managed_fleet(request, fleet_id)
    if error:
        return error
    VoiceGrant.objects.filter(
        character_id=payload.character_id, fleet=fleet, expires_at__isnull=True
    ).update(expires_at=timezone.now())
    VoiceAuditEvent.record(
        VoiceAuditEvent.KIND_KICK,
        character_id=payload.character_id,
        fleet_id=fleet.id,
        actor=request.user,
    )
    publish_character(payload.character_id)
    identity = VoiceIdentity.objects.filter(
        character_id=payload.character_id
    ).first()
    if identity:
        queue_kick(identity.id, payload.message or "Removed by the FC.")
    return 204, None
