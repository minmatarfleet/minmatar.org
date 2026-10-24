"""POST /ping-preview — the start ping the fleet form's details would send."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.characters import user_primary_character
from groups.helpers.feature_access import require_feature

from fleets.endpoints.schemas import (
    FleetPingPreviewRequest,
    FleetPingPreviewResponse,
)
from fleets.helpers.fleet_location import resolve_scheduled_fleet_location
from fleets.helpers.schedule_fleet import resolve_host_group
from fleets.helpers.start_ping import build_start_ping
from fleets.models import EveFleet, EveFleetAudience

PATH = "/ping-preview"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: FleetPingPreviewResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    "description": (
        "The Discord start ping for these fleet details, built by the same "
        "code as the real ping (a group fleet: the group's channel and "
        "role). channel_name is null when there is no channel to ping. "
        "Needs fleets.create, or, with host_group_id, the group's fleet "
        "publishing right."
    ),
}

FLEET_TYPE_LABELS = dict(EveFleet.fleet_types)


def post_ping_preview(request, payload: FleetPingPreviewRequest):
    host_group = None
    audience = None
    if payload.host_group_id:
        host_group = resolve_host_group(request.user, payload.host_group_id)
        if isinstance(host_group, tuple):
            return host_group
    else:
        denied = require_feature(request.user, "fleets.create")
        if denied:
            return denied
        if payload.audience_id:
            audience = EveFleetAudience.objects.filter(
                id=payload.audience_id
            ).first()
            if audience is None:
                return 400, ErrorResponse.new("Audience does not exist")

    location = resolve_scheduled_fleet_location(payload.location_id)
    if isinstance(location, tuple):
        location = None

    fleet_type = payload.type.value
    ping = build_start_ping(
        fleet_id=0,
        fleet_type_label=FLEET_TYPE_LABELS.get(fleet_type, fleet_type),
        location_name=location.location_name if location else None,
        audience=audience,
        host_group=host_group,
        fc_character=user_primary_character(request.user),
        description=payload.description,
    )
    if ping is None:
        return 400, ErrorResponse.new("Pick an audience or a tribe group")

    channel_name = ping.channel_name
    if host_group is not None and ping.channel_id:
        # pylint: disable=import-outside-toplevel
        from tribes.helpers.discord_channels import channel_name as lookup

        channel_name = lookup(ping.channel_id)
    return FleetPingPreviewResponse(
        channel_name=channel_name if ping.channel_id else None,
        payload=ping.payload,
    )
