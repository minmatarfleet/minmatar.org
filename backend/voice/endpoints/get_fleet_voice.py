"""GET /api/voice/fleets/{fleet_id}: the fleet's voice, for its Settings tab."""

from app.errors import ErrorResponse
from eveonline.models import EveCharacter
from fleets.models import EveFleet
from groups.helpers.feature_access import can_use_feature
from voice import channels
from voice.endpoints.base import router
from voice.endpoints.fleet_helpers import AUTH
from voice.endpoints.schemas import VoiceCoFc, VoiceFleetResponse
from voice.models import VoiceChannelLease, VoiceGrant
from voice.permissions import can_manage_voice, is_voice_admin


@router.get(
    "/fleets/{fleet_id}",
    summary="A fleet's voice: branch, co-FCs, wing channels",
    auth=AUTH,
    response={200: VoiceFleetResponse, 404: ErrorResponse},
)
def get_fleet_voice(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if fleet is None or not can_use_feature(
        request.user, "fleets.view", fleet=fleet
    ):
        return 404, ErrorResponse(detail="Fleet not found.")
    manage = can_manage_voice(request.user, fleet)
    lease = (
        VoiceChannelLease.active().filter(fleet=fleet).first()
        if manage
        else None
    )
    co_fcs = []
    if manage:
        ids = list(
            VoiceGrant.objects.filter(
                fleet=fleet,
                source=VoiceGrant.SOURCE_CO_FC,
                expires_at__isnull=True,
            ).values_list("character_id", flat=True)
        )
        names = dict(
            EveCharacter.objects.filter(character_id__in=ids).values_list(
                "character_id", "character_name"
            )
        )
        co_fcs = [
            VoiceCoFc(character_id=i, character_name=names.get(i, str(i)))
            for i in ids
        ]
    return VoiceFleetResponse(
        fleet_id=fleet.id,
        uses_mumble=fleet.uses_mumble,
        can_manage_voice=manage,
        can_ban=is_voice_admin(request.user),
        branch=lease.branch if lease else None,
        branch_name=channels.branch_name(lease.branch) if lease else None,
        wing_channels=(lease.wing_channels or {}) if lease else {},
        channel_choices=list(channels.BRANCH_SUBCHANNELS),
        co_fcs=co_fcs,
    )
