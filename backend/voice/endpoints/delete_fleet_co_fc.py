"""DELETE /api/voice/fleets/{fleet_id}/co-fcs/{character_id}: remove a co-FC."""

from django.utils import timezone

from app.errors import ErrorResponse
from voice.endpoints.base import router
from voice.endpoints.fleet_helpers import AUTH, managed_fleet
from voice.models import VoiceAuditEvent, VoiceGrant
from voice.publisher import publish_character


@router.delete(
    "/fleets/{fleet_id}/co-fcs/{character_id}",
    summary="Remove a co-FC",
    auth=AUTH,
    response={204: None, 403: ErrorResponse, 404: ErrorResponse},
)
def delete_fleet_co_fc(request, fleet_id: int, character_id: int):
    fleet, error = managed_fleet(request, fleet_id)
    if error:
        return error
    VoiceGrant.objects.filter(
        character_id=character_id,
        fleet=fleet,
        source=VoiceGrant.SOURCE_CO_FC,
        expires_at__isnull=True,
    ).update(expires_at=timezone.now())
    VoiceAuditEvent.record(
        VoiceAuditEvent.KIND_CO_FC,
        character_id=character_id,
        fleet_id=fleet.id,
        actor=request.user,
        added=False,
    )
    publish_character(character_id)
    return 204, None
