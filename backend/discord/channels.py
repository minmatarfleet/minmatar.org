import logging

import requests
from django.db.models import Q

from discord.client import DiscordClient
from discord.models import DiscordGuild

logger = logging.getLogger(__name__)
discord = DiscordClient()

ADMIN_PICKER_CHANNEL_TYPES = {"text", "voice", "stage", "forum"}
VOICE_TRACKING_CHANNEL_TYPES = {"voice", "stage"}
CAPITAL_PING_CHANNEL_TYPES = {"text", "forum"}
AMARR_FLEET_PING_CHANNEL_TYPES = {"text", "forum"}
LP_BUYBACK_CHANNEL_TYPES = {"forum"}
LP_CONVERSION_ALERT_CHANNEL_TYPES = {"text"}
BUYBACK_CHANNEL_TYPES = {"forum"}


def fetch_guild_channels(guild_id=None):
    """Return guild channels from the Discord API."""
    try:
        return discord.get_guild_channels(guild_id=guild_id)
    except requests.RequestException:
        logger.exception("Failed to fetch Discord guild channels")
        return []


def admin_picker_guilds():
    """Active guilds whose channels the admin may pick for pings, voice
    tracking and buyback threads.

    A corporation's own server (the bot only makes its invites) stays out:
    listing it costs a Discord call on every form load, and an alliance
    ping must never be pointed at it by mistake. It comes back when it is
    also the alliance's or a tribe's server.
    """
    return (
        DiscordGuild.objects.filter(is_active=True)
        .filter(
            Q(is_primary=True)
            | Q(tribe_group_bindings__isnull=False)
            | Q(corporations__isnull=True)
        )
        .distinct()
        .order_by("name")
    )


def fetch_active_guild_channels():
    """Return channels for every guild the admin pickers list."""
    channels = []
    for guild in admin_picker_guilds():
        channels.extend(fetch_guild_channels(guild_id=guild.guild_id))
    return channels


def get_guild_channel(channel_id: int, guild_id=None):
    """Return a single guild channel by ID, or None if not found."""
    channel_list = (
        fetch_guild_channels(guild_id=guild_id)
        if guild_id is not None
        else fetch_active_guild_channels()
    )
    for channel in channel_list:
        if channel["id"] == channel_id:
            return channel
    return None
