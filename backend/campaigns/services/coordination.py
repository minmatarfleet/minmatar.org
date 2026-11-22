"""Coordination Discord: the server a campaign is run from (admins only).

A campaign is coordinated from our own server unless an admin links it to
another server the bot has been added to as administrator. The admin picks
the intel, timerboard, fleet schedule and fleet pings channels there
(``services.discord_posts`` says what goes in each). Only servers the bot is
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
# The channels picked per server, as <slot>_channel_id on links and
# coordination_<slot>_channel_id on the campaign.
CHANNEL_SLOTS = ("timers", "fleets", "intel", "schedule")


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


def bot_configured() -> bool:
    return bool(
        settings.DISCORD_CLIENT_ID
        and settings.DISCORD_CAMPAIGN_BOT_REDIRECT_URL
    )


def authorize_url(state: str) -> str:
    """Discord's page for adding the bot to a server as an administrator.

    Our Discord application requires the OAuth2 code grant (the corporation
    and tribe bot flows need it), so a plain ``scope=bot`` link is refused:
    the install has to come back to our callback with a code.
    """
    query = urlencode(
        {
            "client_id": settings.DISCORD_CLIENT_ID,
            "scope": "bot",
            "permissions": ADMINISTRATOR,
            "integration_type": 0,
            "response_type": "code",
            "redirect_uri": settings.DISCORD_CAMPAIGN_BOT_REDIRECT_URL,
            "state": state,
        }
    )
    return f"https://discord.com/oauth2/authorize?{query}"


def connect_path(campaign: Campaign, purpose: str) -> str:
    """The API path that starts a bot install for this campaign; the page
    adds the viewer's token."""
    if not bot_configured():
        return ""
    return (
        f"/api/campaigns/{campaign.slug}/discord/bot/connect?purpose={purpose}"
    )


def remember_guild(guild: dict) -> None:
    """Note a server the bot was just added to, so it can be picked before
    the next guild sync."""
    DiscordGuild.objects.update_or_create(
        guild_id=int(guild["id"]),
        defaults={"name": guild.get("name") or "", "is_active": True},
    )


def link_out(link, with_channels: bool = True) -> dict:
    channels = text_channels(link.guild_id) if with_channels else []
    return {
        "id": link.id,
        "guild_id": str(link.guild_id),
        "guild_name": link.guild_name,
        **{
            f"{slot}_channel_id": _id(getattr(link, f"{slot}_channel_id"))
            for slot in CHANNEL_SLOTS
        },
        "linked_by": _linker_name(link),
        "channels": channels or [],
        "channels_unavailable": channels is None,
    }


def _id(value) -> str | None:
    return str(value) if value else None


def _linker_name(link) -> str:
    user = link.linked_by
    if user is None:
        return ""
    # Imported here: eveonline imports campaigns models at load time.
    from eveonline.models import EvePlayer  # pylint: disable=C0415

    player = (
        EvePlayer.objects.filter(user=user)
        .select_related("primary_character")
        .first()
    )
    if player and player.primary_character:
        return player.primary_character.character_name
    return user.username


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
        **{
            f"{slot}_channel_id": (
                _id(getattr(campaign, f"coordination_{slot}_channel_id"))
                if same_server
                else None
            )
            for slot in CHANNEL_SLOTS
        },
        "servers": servers(),
        "channels": channels or [],
        "channels_unavailable": channels is None,
        "invite_url": connect_path(campaign, "ours"),
        "link_url": connect_path(campaign, "link"),
        "links": [link_out(link) for link in campaign.discord_links.all()],
    }
