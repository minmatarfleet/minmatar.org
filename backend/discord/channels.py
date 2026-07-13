import logging

import requests

from discord.client import DiscordClient
from discord.models import DiscordGuild

logger = logging.getLogger(__name__)
discord = DiscordClient()

ADMIN_PICKER_CHANNEL_TYPES = {"text", "voice", "stage", "forum"}
VOICE_TRACKING_CHANNEL_TYPES = {"voice", "stage"}
CAPITAL_PING_CHANNEL_TYPES = {"text", "forum"}


def fetch_guild_channels(guild_id=None):
    """Return guild channels from the Discord API."""
    try:
        return discord.get_guild_channels(guild_id=guild_id)
    except requests.RequestException:
        logger.exception("Failed to fetch Discord guild channels")
        return []


def fetch_active_guild_channels():
    """Return channels for all active tracked guilds."""
    channels = []
    for guild in DiscordGuild.objects.filter(is_active=True).order_by("name"):
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
