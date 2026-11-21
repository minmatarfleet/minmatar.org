"""One endpoint: see the function below."""

from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import require_feature

from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.models import Campaign
from campaigns.services import coordination


def _snowflake(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


@router.put(
    "/{slug}/coordination",
    response={
        200: schemas.CampaignCoordinationOut,
        400: ErrorResponse,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def put_coordination(
    request, slug: str, payload: schemas.CampaignCoordinationRequest
):
    """Link the campaign to a server the bot is in, and pick its timers and
    fleet pings channels there. Admins only."""
    denied = require_feature(request.user, coordination.FEATURE)
    if denied:
        return denied
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()

    server_id = _snowflake(payload.guild_id) or coordination.guild_id(campaign)
    if not server_id or not coordination.is_bot_server(server_id):
        return 400, {"detail": "The bot is not in that server."}
    channel_ids = {
        name: _snowflake(value)
        for name, value in (
            ("timers", payload.timers_channel_id),
            ("fleets", payload.fleets_channel_id),
        )
    }
    if any(channel_ids.values()):
        channels = coordination.text_channels(server_id)
        if channels is None:
            return 400, {
                "detail": "Discord did not list that server's channels."
            }
        known = {int(channel["id"]) for channel in channels}
        if any(cid and cid not in known for cid in channel_ids.values()):
            return 400, {"detail": "That channel is not in the server."}

    ours = int(settings.DISCORD_GUILD_ID or 0)
    campaign.coordination_guild_id = None if server_id == ours else server_id
    campaign.coordination_timers_channel_id = channel_ids["timers"]
    campaign.coordination_fleets_channel_id = channel_ids["fleets"]
    campaign.save(
        update_fields=[
            "coordination_guild_id",
            "coordination_timers_channel_id",
            "coordination_fleets_channel_id",
        ]
    )
    return coordination.coordination_out(campaign)
