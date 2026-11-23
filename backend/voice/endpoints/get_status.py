"""GET /api/voice/status: can the signed-in main join, and why."""

from app.errors import ErrorResponse
from voice import channels
from voice.access import voice_record
from voice.endpoints.base import router
from voice.endpoints.schemas import (
    VoiceFleetAccess,
    VoiceStatusResponse,
)
from voice.identity import VoiceAuth, request_identity


@router.get(
    "/status",
    summary="Voice access for the signed-in character",
    auth=VoiceAuth(),
    response={200: VoiceStatusResponse, 404: ErrorResponse},
)
def get_status(request):
    identity = request_identity(request)
    if identity is None:
        return 404, ErrorResponse(detail="No character to connect with.")
    record = voice_record(identity.character_id)
    return VoiceStatusResponse(
        character_id=identity.character_id,
        character_name=identity.character_name,
        display_name=record.display_name,
        admitted=record.admitted,
        banned=record.banned,
        reason=record.reason,
        community=channels.GROUP_COMMUNITY in record.server_groups,
        fleets=[
            VoiceFleetAccess(
                fleet_id=access.fleet_id,
                branch=int(branch),
                branch_name=channels.branch_name(int(branch)),
                placement=access.placement,
                commander=access.commander,
            )
            for branch, access in sorted(record.branches.items())
        ],
        certificate_count=identity.certificates.count(),
        signed_in_as="member" if request.user.is_authenticated else "guest",
    )
