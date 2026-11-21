"""Add the bot to a Discord server for a campaign, and pick its channels.

Managers add the bot to the server the campaign is run from ("ours").
Managers and coordinators link more servers ("link") that campaign pings
are forwarded to. Both go through Discord's OAuth2 code grant, which our
application requires; the callback learns the server from the code.
"""

from __future__ import annotations

from app.links import site_url
from campaigns.models import Campaign, CampaignDiscordLink
from campaigns.services import disclosure

SESSION_KEY = "campaign_discord_bot"
PURPOSES = ("ours", "link")


def _may_link(user, campaign: Campaign, purpose: str) -> bool:
    viewer = disclosure.role(user, campaign)
    if purpose == "ours":
        return viewer == disclosure.MANAGER
    return viewer in (disclosure.MANAGER, disclosure.COORDINATOR)


def _may_edit(user, link: CampaignDiscordLink) -> bool:
    if disclosure.is_manager(user, link.campaign):
        return True
    return (
        link.linked_by_id == user.id
        and disclosure.role(user, link.campaign) == disclosure.COORDINATOR
    )


def _snowflake(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


def _return_url(campaign: Campaign | None, user) -> str:
    if campaign is None:
        return site_url("/campaigns/")
    if user is not None and disclosure.is_manager(user, campaign):
        return site_url(f"/campaigns/{campaign.slug}/#settings")
    return site_url(f"/campaigns/{campaign.slug}/#discord")


def _with_params(url: str, params: str) -> str:
    base, _, fragment = url.partition("#")
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{params}" + (f"#{fragment}" if fragment else "")
