"""Coordination Discord: the server a campaign is run from (admins only).

A campaign is coordinated from our own server unless an admin links it to
another server the bot has been added to as administrator. The admin picks
a timers channel and a fleet pings channel there. Only servers the bot is
in (``discord.DiscordGuild``, kept by the guild sync) can be picked.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.conf import settings

from campaigns.models import Campaign
from discord.client import DiscordClient
from discord.models import DiscordGuild

logger = logging.getLogger(__name__)

FEATURE = "campaigns.coordination"
# Discord's Administrator permission bit (the invite asks for it).
ADMINISTRATOR = 8
TEXT_CHANNEL_TYPES = ("text",)


def servers() -> list[dict]:
    """Servers the bot is in, ours first."""
    rows = DiscordGuild.objects.filter(is_active=True).order_by(
        "-is_primary", "name"
    )
    return [
        {
            "id": str(row.guild_id),
            "name": row.name,
            "is_primary": row.is_primary,
            "is_administrator": row.bot_is_administrator,
        }
        for row in rows
    ]


def guild_id(campaign: Campaign) -> int | None:
    stored = campaign.coordination_guild_id
    return stored or (int(settings.DISCORD_GUILD_ID or 0) or None)


def is_bot_server(server_id: int) -> bool:
    return DiscordGuild.objects.filter(
        guild_id=server_id, is_active=True
    ).exists() or server_id == int(settings.DISCORD_GUILD_ID or 0)


def text_channels(server_id: int | None) -> list[dict] | None:
    """The server's text channels, or None when Discord could not say."""
    if not server_id:
        return []
    try:
        channels = DiscordClient().get_guild_channels(server_id)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Could not list channels for server %s", server_id)
        return None
    return sorted(
        (
            {"id": str(channel["id"]), "name": channel["name"]}
            for channel in channels
            if channel.get("type") in TEXT_CHANNEL_TYPES
        ),
        key=lambda channel: channel["name"],
    )


def invite_url() -> str:
    """Discord's page for adding the bot to another server as an
    administrator. Empty when the bot's client id is not configured."""
    if not settings.DISCORD_CLIENT_ID:
        return ""
    query = urlencode(
        {
            "client_id": settings.DISCORD_CLIENT_ID,
            "scope": "bot",
            "permissions": ADMINISTRATOR,
            "integration_type": 0,
        }
    )
    return f"https://discord.com/oauth2/authorize?{query}"


def coordination_out(campaign: Campaign, server_id: int | None = None) -> dict:
    """What the settings section shows. ``server_id`` lists another
    server's channels while an admin is choosing one."""
    selected = server_id or guild_id(campaign)
    channels = text_channels(selected)
    same_server = selected == guild_id(campaign)
    known = {row["id"]: row["name"] for row in servers()}
    return {
        "guild_id": str(selected) if selected else None,
        "guild_name": known.get(str(selected), "") if selected else "",
        "is_default": not campaign.coordination_guild_id,
        "timers_channel_id": (
            str(campaign.coordination_timers_channel_id)
            if same_server and campaign.coordination_timers_channel_id
            else None
        ),
        "fleets_channel_id": (
            str(campaign.coordination_fleets_channel_id)
            if same_server and campaign.coordination_fleets_channel_id
            else None
        ),
        "servers": servers(),
        "channels": channels or [],
        "channels_unavailable": channels is None,
        "invite_url": invite_url(),
    }
