"""POST /api/voice/fleets/{fleet_id}/co-fcs: add a co-FC to Command."""

from app.errors import ErrorResponse
from voice.endpoints.base import router
from voice.endpoints.fleet_helpers import AUTH, managed_fleet
from voice.endpoints.schemas import VoiceCharacterRequest
from voice.models import VoiceAuditEvent, VoiceGrant
from voice.publisher import publish_character


@router.post(
    "/fleets/{fleet_id}/co-fcs",
    summary="Add a co-FC (Commanders in this fleet's branch)",
    auth=AUTH,
    response={204: None, 403: ErrorResponse, 404: ErrorResponse},
)
def post_fleet_co_fc(request, fleet_id: int, payload: VoiceCharacterRequest):
    fleet, error = managed_fleet(request, fleet_id)
    if error:
        return error
    VoiceGrant.objects.update_or_create(
        character_id=payload.character_id,
        fleet=fleet,
        source=VoiceGrant.SOURCE_CO_FC,
        role=VoiceGrant.ROLE_COMMANDER,
        defaults={"expires_at": None},
    )
    VoiceAuditEvent.record(
        VoiceAuditEvent.KIND_CO_FC,
        character_id=payload.character_id,
        fleet_id=fleet.id,
        actor=request.user,
        added=True,
    )
    publish_character(payload.character_id)
    return 204, None
