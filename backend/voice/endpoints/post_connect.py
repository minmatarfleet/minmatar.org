"""POST /api/voice/connect: a one-time mumble:// link for the main."""

from app.errors import ErrorResponse
from voice.access import voice_record
from voice.connect import TOKEN_TTL, mint_token, mumble_url
from voice.endpoints.base import router
from voice.endpoints.schemas import VoiceConnectResponse
from voice.identity import VoiceAuth, request_identity
from voice.publisher import publish_character


@router.post(
    "/connect",
    summary="Mint a one-time Mumble link",
    description=(
        "Returns a mumble:// link carrying a one-time password that expires "
        "in 2 minutes. The first connection binds the Mumble certificate."
    ),
    auth=VoiceAuth(),
    response={
        200: VoiceConnectResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def post_connect(request):
    identity = request_identity(request)
    if identity is None:
        return 404, ErrorResponse(detail="No character to connect with.")
    record = voice_record(identity.character_id)
    if not record.admitted:
        return 403, ErrorResponse(detail=record.reason)
    publish_character(identity.character_id)
    token = mint_token(identity)
    return VoiceConnectResponse(
        url=mumble_url(identity, token),
        expires_in_seconds=int(TOKEN_TTL.total_seconds()),
    )
