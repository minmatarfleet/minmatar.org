"""POST /api/voice/internal/redeem: spend a connect token."""

from voice.connect import redeem_token
from voice.endpoints.base import router
from voice.endpoints.internal_auth import InternalSecret, record_for
from voice.endpoints.schemas import VoiceInternalRedeemRequest


@router.post(
    "/internal/redeem",
    auth=InternalSecret(),
    include_in_schema=False,
    response={200: dict, 404: dict},
)
def post_internal_redeem(request, payload: VoiceInternalRedeemRequest):
    """Spend a connect token (the Mumble password) and bind the certificate."""
    return record_for(redeem_token(payload.password, payload.cert_hash))
