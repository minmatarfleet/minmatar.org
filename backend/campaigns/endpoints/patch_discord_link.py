"""One endpoint: see the function below."""

from __future__ import annotations

from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.discord_link_helpers import _may_edit, _snowflake
from campaigns.models import CampaignDiscordLink
from campaigns.services import coordination, discord_posts


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
    """Pick the intel, timerboard, fleet schedule and fleet pings channels
    on a linked server."""
    link = get_object_or_404(
        CampaignDiscordLink.objects.select_related("campaign", "linked_by"),
        campaign__slug=slug,
        id=link_id,
    )
    if not _may_edit(request.user, link):
        return 403, {"detail": "Not authorised"}
    channel_ids = {
        slot: _snowflake(getattr(payload, f"{slot}_channel_id"))
        for slot in coordination.CHANNEL_SLOTS
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
    for slot, channel_id in channel_ids.items():
        setattr(link, f"{slot}_channel_id", channel_id)
    link.save(update_fields=[f"{slot}_channel_id" for slot in channel_ids])
    discord_posts.queue_all_board_refreshes(link.campaign_id)
    return coordination.link_out(link)
