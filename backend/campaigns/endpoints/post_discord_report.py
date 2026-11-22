"""Add a structure or a timer from /campaign-timer or /campaign-structure.

Only the bot calls this, with the server the command ran in and the
reporter's Discord id (``services.discord_reports`` decides who may).
"""

from __future__ import annotations

from django.db import transaction

from app.errors import ErrorResponse
from authentication import AuthBearer, require_service_account
from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.services import discord_reports
from campaigns.services.discord_posts import campaign_url


@router.post(
    "/discord/report",
    response={
        200: schemas.DiscordReportResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def report(request, payload: schemas.DiscordReportRequest):
    """Add a structure or a timer from a Discord command."""
    require_service_account(request)
    try:
        campaign, user = discord_reports.pick_campaign(
            payload.guild_id, payload.discord_user_id, payload.campaign
        )
    except discord_reports.ReportError as exc:
        return 403, {"detail": str(exc)}
    try:
        with transaction.atomic():
            if payload.kind == "timer":
                timer = discord_reports.report_timer(
                    campaign,
                    user,
                    structure_type=payload.structure_type,
                    state=payload.timer_state,
                    selected_item_window=payload.selected_item_window,
                    corporation_name=payload.corporation_name,
                    alliance_name=payload.alliance_name,
                )
                stamp = int(timer.timer.timestamp())
                message = (
                    f"Timer added to {campaign.name}: {timer.system_name} - "
                    f"{timer.name}, {timer.get_state_display().lower()} "
                    f"<t:{stamp}:F> (<t:{stamp}:R>)."
                )
                tab = "timers"
            else:
                structure = discord_reports.report_structure(
                    campaign,
                    user,
                    structure_type=payload.structure_type,
                    selected_item_window=payload.selected_item_window,
                    corporation_name=payload.corporation_name,
                    alliance_name=payload.alliance_name,
                    reinforce_hour=payload.reinforce_hour,
                )
                message = (
                    f"Structure added to {campaign.name}: "
                    f"{structure.system_name} - {structure.name}."
                )
                tab = "structures"
    except discord_reports.ReportError as exc:
        return 400, {"detail": str(exc)}
    return {
        "message": message,
        "campaign": campaign.name,
        "url": campaign_url(campaign, tab),
    }
