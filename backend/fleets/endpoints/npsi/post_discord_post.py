"""POST /npsi-events/{event_id}/discord-post — alias of discord-create."""

from fleets.endpoints.npsi.post_discord_create import (
    ROUTE_SPEC,
    post_npsi_discord_create,
)
from fleets.endpoints.npsi.schemas import DiscordNpsiActionRequest

PATH = "/npsi-events/{event_id}/discord-post"
METHOD = "post"

__all__ = ["PATH", "METHOD", "ROUTE_SPEC", "post_npsi_discord_post"]


def post_npsi_discord_post(
    request, event_id: int, payload: DiscordNpsiActionRequest
):
    return post_npsi_discord_create(request, event_id, payload)
