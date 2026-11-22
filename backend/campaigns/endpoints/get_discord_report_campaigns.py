"""The campaigns a Discord user may report to from a server: the
/campaign-timer and /campaign-structure autocomplete. Bot only."""

from __future__ import annotations

from app.errors import ErrorResponse
from authentication import AuthBearer, require_service_account
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.services import discord_reports


@router.get(
    "/discord/report-campaigns",
    response={200: list[schemas.DiscordReportCampaign], 403: ErrorResponse},
    auth=AuthBearer(),
)
def report_campaigns(request, guild_id: int, discord_user_id: int):
    """The campaigns this Discord user may report to from this server."""
    require_service_account(request)
    return [
        {"slug": campaign.slug, "name": campaign.name}
        for campaign in discord_reports.reportable_campaigns(
            guild_id, discord_user_id
        )
    ]
