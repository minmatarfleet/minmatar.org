"""One endpoint: see the function below."""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User
from requests import RequestException

from campaigns.endpoints.base import router
from campaigns.endpoints.discord_link_helpers import (
    SESSION_KEY,
    _may_link,
    _return_url,
    _with_params,
)
from campaigns.models import Campaign, CampaignDiscordLink
from campaigns.services import coordination
from discord.client import DiscordClient, DiscordError
from users.redirects import oauth_redirect

logger = logging.getLogger(__name__)


@router.get(
    "/discord/bot/callback",
    response={302: None},
    include_in_schema=False,
)
def bot_callback(
    request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """Discord sends the person back after adding the bot."""
    pending = request.session.pop(SESSION_KEY, None) or {}
    request.session.modified = True
    campaign = Campaign.objects.filter(id=pending.get("campaign_id")).first()
    user = User.objects.filter(id=pending.get("user_id")).first()
    return_url = _return_url(campaign, user)

    def fail(reason: str):
        logger.info("Campaign Discord bot link failed: %s", reason)
        return oauth_redirect(
            _with_params(return_url, f"discord_bot_error={reason}")
        )

    if error:
        return fail("denied" if error == "access_denied" else "oauth_error")
    if not pending.get("state") or state != pending["state"]:
        return fail("session_expired")
    purpose = pending.get("purpose")
    if not code or campaign is None or user is None:
        return fail("oauth_error")
    if not _may_link(user, campaign, purpose):
        return fail("not_allowed")

    try:
        guild = DiscordClient().exchange_bot_code(
            code, settings.DISCORD_CAMPAIGN_BOT_REDIRECT_URL
        )
    except (DiscordError, RequestException) as exc:
        logger.warning("Campaign Discord bot code exchange failed: %s", exc)
        return fail("exchange_failed")

    coordination.remember_guild(guild)
    guild_id = int(guild["id"])
    if purpose == "ours":
        ours = int(settings.DISCORD_GUILD_ID or 0)
        campaign.coordination_guild_id = None if guild_id == ours else guild_id
        campaign.save(update_fields=["coordination_guild_id"])
    else:
        CampaignDiscordLink.objects.update_or_create(
            campaign=campaign,
            guild_id=guild_id,
            defaults={
                "guild_name": guild.get("name") or "",
                "linked_by": user,
            },
        )
    logger.info(
        "Campaign %s: bot added to Discord guild %s (%s)",
        campaign.id,
        guild_id,
        purpose,
    )
    return oauth_redirect(_with_params(return_url, "discord_bot=connected"))
