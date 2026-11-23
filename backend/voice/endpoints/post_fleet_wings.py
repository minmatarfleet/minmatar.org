"""POST /api/voice/fleets/{fleet_id}/wings: in-game wing -> channel mapping."""

from app.errors import ErrorResponse
from discord.outbox import on_commit_enqueue
from voice import channels
from voice.endpoints.base import router
from voice.endpoints.fleet_helpers import AUTH, managed_fleet
from voice.endpoints.schemas import VoiceWingsRequest
from voice.models import VoiceAuditEvent, VoiceChannelLease
from voice.publisher import publish_leases
from voice.tasks import publish_fleet_wing_pilots


@router.post(
    "/fleets/{fleet_id}/wings",
    summary="Send in-game wings to channels on first placement",
    auth=AUTH,
    response={
        204: None,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
)
def post_fleet_wings(request, fleet_id: int, payload: VoiceWingsRequest):
    fleet, error = managed_fleet(request, fleet_id)
    if error:
        return error
    mapping = {}
    for wing_id, channel in payload.wing_channels.items():
        if (
            not str(wing_id).isdigit()
            or channel not in channels.BRANCH_SUBCHANNELS
        ):
            return 400, ErrorResponse(
                detail=f"Unknown wing or channel: {wing_id}"
            )
        mapping[str(int(wing_id))] = channel
    lease = VoiceChannelLease.active().filter(fleet=fleet).first()
    if lease is None:
        return 409, ErrorResponse(detail="The fleet has no voice branch yet.")
    lease.wing_channels = mapping
    lease.save(update_fields=["wing_channels"])
    VoiceAuditEvent.record(
        VoiceAuditEvent.KIND_WINGS, fleet_id=fleet.id, actor=request.user
    )
    publish_leases()
    on_commit_enqueue(
        publish_fleet_wing_pilots,
        (fleet.id,),
        context=f"voice wings fleet {fleet.id}",
    )
    return 204, None
