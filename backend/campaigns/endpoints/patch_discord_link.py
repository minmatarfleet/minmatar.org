"""One endpoint: see the function below."""

from __future__ import annotations

from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.discord_link_helpers import _may_edit, _snowflake
from campaigns.models import CampaignDiscordLink
from campaigns.services import coordination


@router.patch(
    "/{slug}/discord-links/{link_id}",
    response={
        200: schemas.CampaignDiscordLinkOut,
        400: ErrorResponse,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def update_link(
    request,
    slug: str,
    link_id: int,
    payload: schemas.CampaignDiscordLinkRequest,
):
    """Pick the timers and fleet pings channels on a linked server."""
    link = get_object_or_404(
        CampaignDiscordLink.objects.select_related("campaign", "linked_by"),
        campaign__slug=slug,
        id=link_id,
    )
    if not _may_edit(request.user, link):
        return 403, {"detail": "Not authorised"}
    channel_ids = {
        "timers": _snowflake(payload.timers_channel_id),
        "fleets": _snowflake(payload.fleets_channel_id),
    }
    if any(channel_ids.values()):
        channels = coordination.text_channels(link.guild_id)
        if channels is None:
            return 400, {
                "detail": "Discord did not list that server's channels."
            }
        known = {int(channel["id"]) for channel in channels}
        if any(cid and cid not in known for cid in channel_ids.values()):
            return 400, {"detail": "That channel is not in the server."}
    link.timers_channel_id = channel_ids["timers"]
    link.fleets_channel_id = channel_ids["fleets"]
    link.save(update_fields=["timers_channel_id", "fleets_channel_id"])
    return coordination.link_out(link)
