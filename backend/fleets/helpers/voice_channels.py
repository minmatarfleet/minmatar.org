"""The Discord voice channel a fleet talks in.

A Discord voice option (``FleetVoiceOption``) names a server
(``discord_guild_id``). The fleet form lists that server's voice channels,
starting on the option's ``discord_channel_id``, and the FC's pick is stored
on the fleet (``voice_channel_id``, ``voice_channel_name``). The start ping
and the MOTD link it.

Channels come from Discord, cached for a few minutes per server. A channel
@everyone can't see or join, and one an admin marked ``hide_from_fleets``
on its DiscordChannel row, is left out.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.core.cache import cache

from app.errors import ErrorResponse
from discord.client import GUILD_ID, DiscordClient
from discord.models import DiscordChannel

logger = logging.getLogger(__name__)

CACHE_SECONDS = 300
CACHE_KEY = "fleets:voice_channels:{}"
UNAVAILABLE = "unavailable"
UNAVAILABLE_SECONDS = 60
# Discord channel types: voice and stage.
VOICE_TYPES = (2, 13)
CATEGORY_TYPE = 4
VIEW_CHANNEL = 1 << 10
CONNECT = 1 << 20
ROLE_OVERWRITE = 0


@dataclass(frozen=True)
class VoiceChannel:
    id: int
    name: str
    category: str


def channel_url(guild_id: int, channel_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}"


def _everyone_denied(channel: dict, guild_id: int) -> bool:
    for overwrite in channel.get("permission_overwrites") or []:
        if overwrite.get("type") != ROLE_OVERWRITE:
            continue
        if str(overwrite.get("id")) != str(guild_id):
            continue
        return bool(int(overwrite.get("deny") or 0) & (VIEW_CHANNEL | CONNECT))
    return False


def _fetch(guild_id: int) -> list[dict] | None:
    key = CACHE_KEY.format(guild_id)
    cached = cache.get(key)
    if cached == UNAVAILABLE:
        return None
    if cached is not None:
        return cached
    try:
        raw = DiscordClient().get_guild_channels_raw(guild_id)
    except Exception:  # pylint: disable=broad-exception-caught
        # Rate limits, HTTP errors, the bot not on the server: the form
        # still works, it just lists no channels for a minute.
        logger.warning("Voice channels for guild %s unavailable", guild_id)
        cache.set(key, UNAVAILABLE, UNAVAILABLE_SECONDS)
        return None
    categories = {
        str(c["id"]): c for c in raw if c.get("type") == CATEGORY_TYPE
    }
    rows = []
    for channel in raw:
        if channel.get("type") not in VOICE_TYPES:
            continue
        parent = categories.get(str(channel.get("parent_id")))
        # A channel without its own @everyone rule follows its category's.
        own_rule = any(
            o.get("type") == ROLE_OVERWRITE
            and str(o.get("id")) == str(guild_id)
            for o in channel.get("permission_overwrites") or []
        )
        source = channel if own_rule or parent is None else parent
        if _everyone_denied(source, guild_id):
            continue
        rows.append(
            {
                "id": int(channel["id"]),
                "name": channel["name"],
                "category": parent["name"] if parent else "",
                "order": (
                    parent.get("position", 0) if parent else -1,
                    channel.get("position", 0),
                ),
            }
        )
    rows.sort(key=lambda row: row["order"])
    cache.set(key, rows, CACHE_SECONDS)
    return rows


def voice_channels(option) -> list[VoiceChannel] | None:
    """The option's server's voice channels, in Discord's order.

    [] for Mumble or a Discord option without a server; None when Discord
    can't be reached.
    """
    if option is None or option.is_mumble or not option.discord_guild_id:
        return []
    rows = _fetch(int(option.discord_guild_id))
    if rows is None:
        return None
    hidden = set(
        DiscordChannel.objects.filter(
            channel_id__in=[row["id"] for row in rows], hide_from_fleets=True
        ).values_list("channel_id", flat=True)
    )
    return [
        VoiceChannel(row["id"], row["name"], row["category"])
        for row in rows
        if row["id"] not in hidden
    ]


def default_channel_id(option, channels) -> int | None:
    """Where the form starts: the option's channel, else the first one."""
    if not channels:
        return None
    ids = [channel.id for channel in channels]
    if option.discord_channel_id and int(option.discord_channel_id) in ids:
        return int(option.discord_channel_id)
    return ids[0]


def resolve_voice_channel(option, channel_id, current=None):
    """(channel_id, name) to store, or (400, error).

    No channel, a Mumble option, or Discord unreachable stores no channel,
    unless it is the fleet's current one (``current``: (id, name)), which
    it keeps.
    """
    if not channel_id or option is None or option.is_mumble:
        return None, ""
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return 400, ErrorResponse.new(f"No voice channel {channel_id}")
    if current and current[0] == channel_id:
        return current
    channels = voice_channels(option)
    if channels is None:
        return None, ""
    for channel in channels:
        if channel.id == channel_id:
            return channel.id, channel.name
    return 400, ErrorResponse.new(
        f"{option.name} has no voice channel {channel_id}"
    )


def voice_link(fleet) -> tuple[str, str] | None:
    """(name, url) of the fleet's Discord voice channel, or None."""
    option = fleet.effective_voice_option
    if (
        option is None
        or option.is_mumble
        or not option.discord_guild_id
        or not fleet.voice_channel_id
    ):
        return None
    return (
        fleet.voice_channel_name or "Voice",
        channel_url(int(option.discord_guild_id), int(fleet.voice_channel_id)),
    )


def _mumble_label(fleet) -> str:
    """The branch the fleet holds, or the one it will get. An open fleet
    falls back to a restricted branch when another open fleet has Fleet 1,
    so a held lease wins."""
    # pylint: disable=import-outside-toplevel
    from voice.channels import OPEN_BRANCH, branch_name
    from voice.models import VoiceChannelLease

    lease = (
        VoiceChannelLease.active().filter(fleet_id=fleet.id).first()
        if fleet.id
        else None
    )
    if lease is not None:
        name = branch_name(lease.branch)
        if lease.branch == OPEN_BRANCH:
            return f"{name}, open to all members"
        return name
    if fleet.mumble_open:
        return f"{branch_name(OPEN_BRANCH)}, open to all members"
    return "your fleet's branch"


def ping_voice(fleet) -> tuple[str | None, str | None]:
    """(VOICE CHANNEL line text, Join Voice Channel url) for the ping.

    The alliance server's channel is a mention; another server's is a
    markdown link, because Discord can't show a mention across servers.
    Mumble links the /voice page.
    """
    # pylint: disable=import-outside-toplevel
    from app.links import voice_url

    option = fleet.effective_voice_option
    if option is None:
        return None, None
    if option.is_mumble:
        return f"[Mumble]({voice_url()}): {_mumble_label(fleet)}", voice_url()
    link = voice_link(fleet)
    if link is None:
        return (option.name, option.link) if option.link else (None, None)
    name, url = link
    if str(option.discord_guild_id) == str(GUILD_ID):
        return f"<#{fleet.voice_channel_id}>", url
    return f"[{name}]({url}) on {option.name}", url
