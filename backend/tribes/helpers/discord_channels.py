"""The guild's Discord channels, cached, for pickers and previews."""

from __future__ import annotations

import logging

from django.core.cache import cache

from discord.client import DiscordClient

logger = logging.getLogger(__name__)

CACHE_KEY = "tribes:discord:guild_channels"
CACHE_SECONDS = 10 * 60

TEXT_TYPES = ("text",)
VOICE_TYPES = ("voice", "stage")


def guild_channels() -> list[dict]:
    """``[{id, name, type}]`` for the main guild, cached 10 minutes.

    Returns [] (uncached) when Discord can't be reached.
    """
    try:
        cached = cache.get(CACHE_KEY)
    except Exception:  # pylint: disable=broad-exception-caught
        # expected: cache down; fetch from Discord instead
        cached = None
    if cached is not None:
        return cached
    try:
        channels = [
            {"id": c["id"], "name": c["name"], "type": c["type"]}
            for c in DiscordClient().get_guild_channels()
        ]
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Could not list Discord channels", exc_info=True)
        return []
    try:
        cache.set(CACHE_KEY, channels, CACHE_SECONDS)
    except Exception:  # pylint: disable=broad-exception-caught
        # expected: cache down; the list is still returned
        pass
    return channels


def channels_of_kind(kind: str) -> list[dict]:
    """Text channels, or voice channels (stage channels included)."""
    types = VOICE_TYPES if kind == "voice" else TEXT_TYPES
    return sorted(
        (c for c in guild_channels() if c["type"] in types),
        key=lambda c: c["name"].lower(),
    )


def find_channel(channel_id: int | None) -> dict | None:
    if not channel_id:
        return None
    for channel in guild_channels():
        if int(channel["id"]) == int(channel_id):
            return channel
    return None


def channel_name(channel_id: int | None) -> str | None:
    channel = find_channel(channel_id)
    return channel["name"] if channel else None
