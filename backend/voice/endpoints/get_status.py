"""GET /api/voice/status: can the signed-in main join, and why."""

from app.errors import ErrorResponse
from fleets.models import EveFleet
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
    fleets = {
        fleet.id: fleet
        for fleet in EveFleet.objects.filter(
            id__in=[access.fleet_id for access in record.branches.values()]
        ).select_related("created_by")
    }
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
                **(
                    _fleet_summary(fleets.get(access.fleet_id))
                    if access.part_of_fleet or access.commander
                    else {}
                ),
            )
            for branch, access in sorted(record.branches.items())
        ],
        certificate_count=identity.certificates.count(),
        signed_in_as="member" if request.user.is_authenticated else "guest",
    )


def _fleet_summary(fleet: EveFleet | None) -> dict:
    """What a pilot in the fleet, or running it, sees of it.

    Pilots who only have standing access (capitals on standby, campaign
    allies) get the channel but not the fleet's details.
    """
    if fleet is None:
        return {}
    fc = fleet.fleet_commander if fleet.created_by_id else None
    return {
        "fleet_title": fleet.objective or fleet.get_type_display(),
        "start_time": fleet.start_time,
        "fc_name": fc.character_name if fc else None,
    }
