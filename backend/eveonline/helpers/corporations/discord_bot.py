"""A corporation's Discord server, reached through our bot.

The CEO or a director adds the bot to their server from the Settings tab
(Discord's bot install page, with only Create Instant Invite and View
Channel). The bot then keeps one 7-day invite fresh, and the corporation
page links to it, so the link never dies the way a pasted one can.

- Page views never call Discord. The invite is made and rotated by Celery
  (``refresh_corporation_discord_bot``) and stored on the corporation.
- An invite is replaced once it has under ``ROTATE_BEFORE`` left, so any
  link a visitor saw keeps working for days. The old one is left to
  expire, never deleted: at most two of ours sit in the server's list.
- The bot reads no messages and has no other permissions. It only makes
  invites, in the channel it picked (the server's system channel, else the
  first one everyone can see).
- The pasted invite (``discord_invite``) stays as the fallback while the
  bot is setting up or can't make invites.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ratelimit import RateLimitException
from requests import HTTPError, RequestException

from discord.client import DiscordClient, discord_error_code
from discord.models import DiscordGuild
from eveonline.helpers.corporations.discord_invite import (
    discord_settings,
    icon_url,
    public_invite_url,
)
from eveonline.models import EveCorporation

logger = logging.getLogger(__name__)

# Discord's longest invite. Rotated with ROTATE_BEFORE left.
INVITE_MAX_AGE = 7 * 24 * 60 * 60
ROTATE_BEFORE = timedelta(days=3)
# Never hand a visitor an invite about to expire.
PUBLIC_MARGIN = timedelta(hours=1)
# Channels tried when the bot needs a new one; each failure is one call.
PROBE_LIMIT = 5

# Create Instant Invite | View Channel: all the bot asks for.
CREATE_INSTANT_INVITE = 1 << 0
VIEW_CHANNEL = 1 << 10
BOT_PERMISSIONS = CREATE_INSTANT_INVITE | VIEW_CHANNEL

# Text and announcement channels can hold an invite.
INVITE_CHANNEL_TYPES = {0, 5}
CATEGORY = 4

# Discord JSON error codes.
UNKNOWN_CHANNEL = 10003
UNKNOWN_GUILD = 10004
MISSING_ACCESS = 50001
MISSING_PERMISSIONS = 50013

CHANNEL_NAME_MAX = EveCorporation._meta.get_field(
    "discord_bot_channel_name"
).max_length
ICON_MAX = EveCorporation._meta.get_field("discord_bot_guild_icon").max_length
CODE_MAX = EveCorporation._meta.get_field("discord_bot_invite_code").max_length

BOT_FIELDS = [
    "discord_guild",
    "discord_bot_status",
    "discord_bot_guild_icon",
    "discord_bot_channel_id",
    "discord_bot_channel_name",
    "discord_bot_invite_code",
    "discord_bot_invite_expires_at",
    "discord_bot_checked_at",
    "discord_bot_linked_at",
    "discord_bot_linked_by",
]


# What a refresh writes; the link itself (server, who, when) stays as is.
REFRESH_FIELDS = [
    "discord_bot_status",
    "discord_bot_channel_id",
    "discord_bot_channel_name",
    "discord_bot_invite_code",
    "discord_bot_invite_expires_at",
    "discord_bot_checked_at",
]


class DiscordBotError(ValueError):
    """A bot install that can't be linked. `code` names it for the frontend."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class DiscordUnavailable(Exception):
    """Discord didn't answer (rate limit, timeout, 5xx): try again later."""


@dataclass
class Release:
    """What to clean up once a corporation lets go of a server."""

    guild_id: int
    invite_code: str


def bot_configured() -> bool:
    return bool(
        settings.DISCORD_CLIENT_ID and settings.DISCORD_CORP_BOT_REDIRECT_URL
    )


def authorize_url(state: str) -> str:
    """Discord's page for adding the bot to a server the person manages."""
    query = urlencode(
        {
            "client_id": settings.DISCORD_CLIENT_ID,
            "scope": "bot",
            "permissions": BOT_PERMISSIONS,
            # A server install, not a user install.
            "integration_type": 0,
            "response_type": "code",
            "redirect_uri": settings.DISCORD_CORP_BOT_REDIRECT_URL,
            "state": state,
        }
    )
    return f"https://discord.com/oauth2/authorize?{query}"


def is_connected(corporation: EveCorporation) -> bool:
    return bool(corporation.discord_bot_status) and bool(
        corporation.discord_guild_id
    )


def link_guild(
    corporation: EveCorporation, guild: dict, user
) -> Release | None:
    """Point the corporation at the server the bot was just added to.

    `guild` is the server from the OAuth code exchange. Returns the server
    it used before, when there was another one, so the caller can release
    it. Raises DiscordBotError("alliance_server") for the alliance Discord.
    """
    guild_id = int(guild["id"])
    if guild_id == int(settings.DISCORD_GUILD_ID):
        raise DiscordBotError("alliance_server")

    row, _ = DiscordGuild.objects.update_or_create(
        guild_id=guild_id,
        defaults={
            "name": str(guild.get("name") or "")[:255] or str(guild_id),
            "is_active": True,
            "last_seen_at": timezone.now(),
        },
    )
    previous = None
    same_guild = corporation.discord_guild_id == row.pk
    if is_connected(corporation) and not same_guild:
        previous = Release(
            guild_id=corporation.discord_guild.guild_id,
            invite_code=corporation.discord_bot_invite_code,
        )
    if not same_guild:
        # A new server: none of the old channel or invite applies.
        corporation.discord_bot_channel_id = None
        corporation.discord_bot_channel_name = ""
        corporation.discord_bot_invite_code = ""
        corporation.discord_bot_invite_expires_at = None
    if corporation.discord_bot_channel_id is None and guild.get(
        "system_channel_id"
    ):
        corporation.discord_bot_channel_id = int(guild["system_channel_id"])

    corporation.discord_guild = row
    corporation.discord_bot_status = EveCorporation.DISCORD_BOT_PENDING
    corporation.discord_bot_guild_icon = str(guild.get("icon") or "")[
        :ICON_MAX
    ]
    corporation.discord_bot_checked_at = None
    corporation.discord_bot_linked_at = timezone.now()
    corporation.discord_bot_linked_by = user
    corporation.save(update_fields=BOT_FIELDS)
    return previous


def unlink_guild(corporation: EveCorporation) -> Release | None:
    """Stop using the bot for this corporation. The pasted link, if any,
    becomes the page's Discord again. Returns what to release."""
    if not is_connected(corporation):
        return None
    release = Release(
        guild_id=corporation.discord_guild.guild_id,
        invite_code=corporation.discord_bot_invite_code,
    )
    corporation.discord_guild = None
    corporation.discord_bot_status = ""
    corporation.discord_bot_guild_icon = ""
    corporation.discord_bot_channel_id = None
    corporation.discord_bot_channel_name = ""
    corporation.discord_bot_invite_code = ""
    corporation.discord_bot_invite_expires_at = None
    corporation.discord_bot_checked_at = None
    corporation.discord_bot_linked_at = None
    corporation.discord_bot_linked_by = None
    corporation.save(update_fields=BOT_FIELDS)
    return release


def mark_pending(corporation: EveCorporation) -> None:
    """Ask for a fresh setup (after the server fixed the bot's permissions)."""
    corporation.discord_bot_status = EveCorporation.DISCORD_BOT_PENDING
    corporation.save(update_fields=["discord_bot_status"])


def guild_in_use(guild_id: int) -> bool:
    """Whether anything but a released corporation still needs the bot in
    this server: the alliance Discord, a tribe's server, or a corporation
    (including one linked by hand in the admin)."""
    if guild_id == int(settings.DISCORD_GUILD_ID):
        return True
    return (
        DiscordGuild.objects.filter(guild_id=guild_id)
        .filter(
            Q(is_primary=True)
            | Q(tribe_group_bindings__isnull=False)
            | Q(corporations__isnull=False)
        )
        .exists()
    )


def release_guild(guild_id: int, invite_code: str) -> bool:
    """Revoke our invite and leave the server when nothing else uses it.
    Returns whether the bot left. Safe to run twice."""
    client = DiscordClient()
    in_use = guild_in_use(guild_id)
    if invite_code and not _invite_still_ours(guild_id, invite_code):
        try:
            client.delete_invite(invite_code)
        except (RequestException, RateLimitException) as e:
            logger.warning(
                "Couldn't revoke Discord invite %s: %s", invite_code, e
            )
    if in_use:
        return False
    try:
        client.leave_guild(guild_id)
    except (RequestException, RateLimitException) as e:
        logger.warning("Couldn't leave Discord guild %s: %s", guild_id, e)
        return False
    DiscordGuild.objects.filter(guild_id=guild_id).update(is_active=False)
    logger.info("Left Discord guild %s: no corporation uses it", guild_id)
    return True


def _invite_still_ours(guild_id: int, invite_code: str) -> bool:
    """A corporation reconnected and kept this invite: don't revoke it."""
    return EveCorporation.objects.filter(
        discord_guild__guild_id=guild_id,
        discord_bot_invite_code=invite_code,
    ).exists()


def _visible_to_everyone(
    channel: dict, guild_id: int, categories: dict
) -> bool:
    """Whether @everyone can see the channel, judged from the overwrites on
    it, else on its category. Server-wide role permissions aren't read."""

    def everyone_view(overwrites) -> bool | None:
        for overwrite in overwrites or []:
            if str(overwrite.get("id")) != str(guild_id):
                continue
            if int(overwrite.get("deny") or 0) & VIEW_CHANNEL:
                return False
            if int(overwrite.get("allow") or 0) & VIEW_CHANNEL:
                return True
        return None

    own = everyone_view(channel.get("permission_overwrites"))
    if own is not None:
        return own
    parent = categories.get(channel.get("parent_id"))
    if parent is not None:
        inherited = everyone_view(parent.get("permission_overwrites"))
        if inherited is not None:
            return inherited
    return True


def landing_channels(
    channels: list[dict], guild_id: int, preferred: int | None = None
) -> list[dict]:
    """Channels to try for the invite, best first: `preferred` (the server's
    system channel), then in the order Discord lists them. Channels hidden
    from @everyone are skipped: a newcomer would land somewhere they can't
    see."""
    categories = {
        channel["id"]: channel
        for channel in channels
        if channel.get("type") == CATEGORY
    }

    def order(channel):
        parent = categories.get(channel.get("parent_id"))
        # Channels outside a category list above every category.
        parent_position = parent.get("position", 0) if parent else -1
        return (
            0 if preferred and int(channel["id"]) == preferred else 1,
            parent_position,
            channel.get("position", 0),
            int(channel["id"]),
        )

    candidates = [
        channel
        for channel in channels
        if channel.get("type") in INVITE_CHANNEL_TYPES
        and _visible_to_everyone(channel, guild_id, categories)
    ]
    return sorted(candidates, key=order)


def _expiry(invite: dict, now: datetime) -> datetime:
    raw = invite.get("expires_at")
    parsed = parse_datetime(raw) if raw else None
    return parsed or now + timedelta(seconds=INVITE_MAX_AGE)


def _invite_fresh(corporation: EveCorporation, now: datetime) -> bool:
    expires_at = corporation.discord_bot_invite_expires_at
    return bool(
        corporation.discord_bot_invite_code
        and expires_at
        and expires_at - now > ROTATE_BEFORE
    )


def _transient(error: HTTPError) -> bool:
    response = error.response
    return response is None or response.status_code >= 500


def _invite_alive(client: DiscordClient, code: str) -> bool:
    try:
        client.get_invite(code)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return False
        raise
    return True


def _try_channel(
    client: DiscordClient, channel_id: int
) -> tuple[dict | None, int | None]:
    """(invite, None) or (None, Discord error code) for one channel."""
    try:
        return client.create_channel_invite(channel_id, INVITE_MAX_AGE), None
    except HTTPError as e:
        if _transient(e):
            raise
        return None, discord_error_code(e) or 0


def _store_invite(
    corporation: EveCorporation,
    invite: dict,
    channel: dict | None,
    now: datetime,
) -> str:
    corporation.discord_bot_invite_code = str(invite["code"])[:CODE_MAX]
    corporation.discord_bot_invite_expires_at = _expiry(invite, now)
    if channel is not None:
        corporation.discord_bot_channel_id = int(channel["id"])
        corporation.discord_bot_channel_name = str(channel.get("name") or "")[
            :CHANNEL_NAME_MAX
        ]
    elif not corporation.discord_bot_channel_name:
        name = (invite.get("channel") or {}).get("name")
        corporation.discord_bot_channel_name = str(name or "")[
            :CHANNEL_NAME_MAX
        ]
    return EveCorporation.DISCORD_BOT_OK


def _mint(client: DiscordClient, corporation: EveCorporation, now) -> str:
    """Make a new invite, finding a channel that allows it. Returns the
    status to save."""
    guild_id = corporation.discord_guild.guild_id
    tried = None
    if corporation.discord_bot_channel_id:
        tried = corporation.discord_bot_channel_id
        invite, error = _try_channel(client, tried)
        if invite is not None:
            return _store_invite(corporation, invite, None, now)
        if error == UNKNOWN_GUILD:
            return EveCorporation.DISCORD_BOT_REMOVED

    try:
        channels = client.get_guild_channels_raw(guild_id)
    except HTTPError as e:
        if _transient(e):
            raise
        # Unknown Guild or Missing Access: the bot isn't in the server.
        return EveCorporation.DISCORD_BOT_REMOVED

    candidates = [
        channel
        for channel in landing_channels(channels, guild_id)
        if int(channel["id"]) != tried
    ]
    for channel in candidates[:PROBE_LIMIT]:
        invite, error = _try_channel(client, int(channel["id"]))
        if invite is not None:
            return _store_invite(corporation, invite, channel, now)
        if error == UNKNOWN_GUILD:
            return EveCorporation.DISCORD_BOT_REMOVED
    return EveCorporation.DISCORD_BOT_NO_PERMISSION


def refresh_bot_invite(corporation: EveCorporation) -> str | None:
    """Make sure the corporation has a working invite with days left.

    Returns the saved status, or None when there's nothing to do or
    Discord didn't answer (the next run tries again).
    """
    if not is_connected(corporation):
        return None
    guild = corporation.discord_guild
    if (
        not guild.is_active
        and corporation.discord_bot_status
        == EveCorporation.DISCORD_BOT_REMOVED
    ):
        # Already known to be out; the guild sync says when it's back.
        return None

    now = timezone.now()
    client = DiscordClient()
    try:
        if _invite_fresh(corporation, now) and _invite_alive(
            client, corporation.discord_bot_invite_code
        ):
            status = EveCorporation.DISCORD_BOT_OK
        else:
            status = _mint(client, corporation, now)
    except (RequestException, RateLimitException) as e:
        logger.warning(
            "Discord invite refresh for %s failed: %s",
            corporation.corporation_id,
            e,
        )
        return None

    previous_status = corporation.discord_bot_status
    corporation.discord_bot_status = status
    corporation.discord_bot_checked_at = now
    # Only while the link this run started from still stands: a disconnect
    # or a new server meanwhile must not be written over.
    saved = (
        EveCorporation.objects.filter(
            pk=corporation.pk,
            discord_guild_id=corporation.discord_guild_id,
            discord_bot_linked_at=corporation.discord_bot_linked_at,
        )
        .exclude(discord_bot_status="")
        .update(
            **{field: getattr(corporation, field) for field in REFRESH_FIELDS}
        )
    )
    if not saved:
        logger.info(
            "Corporation %s Discord bot changed during a refresh; dropped",
            corporation.corporation_id,
        )
        return None
    if status != previous_status:
        logger.info(
            "Corporation %s Discord bot: %s -> %s",
            corporation.corporation_id,
            previous_status or "-",
            status,
        )
    return status


def bot_invite_url(corporation: EveCorporation) -> str | None:
    """The bot's invite, while it works and has time left."""
    if (
        not is_connected(corporation)
        or corporation.discord_bot_status != EveCorporation.DISCORD_BOT_OK
        or not corporation.discord_guild.is_active
        or not corporation.discord_bot_invite_code
    ):
        return None
    expires_at = corporation.discord_bot_invite_expires_at
    if expires_at is None or expires_at - timezone.now() < PUBLIC_MARGIN:
        return None
    return f"https://discord.gg/{corporation.discord_bot_invite_code}"


def page_invite_url(corporation: EveCorporation) -> str | None:
    """The Discord link the corporation page shows: the bot's invite, else
    the pasted one while it works."""
    return bot_invite_url(corporation) or public_invite_url(corporation)


def bot_settings(corporation: EveCorporation) -> dict:
    connected = is_connected(corporation)
    guild = corporation.discord_guild if connected else None
    return {
        "available": bot_configured(),
        "connected": connected,
        "status": corporation.discord_bot_status or None,
        "guild_name": guild.name if guild else None,
        "icon_url": (
            icon_url(guild.guild_id, corporation.discord_bot_guild_icon)
            if guild
            else None
        ),
        "channel_name": corporation.discord_bot_channel_name or None,
        "invite_url": bot_invite_url(corporation),
        "invite_expires_at": (
            corporation.discord_bot_invite_expires_at if connected else None
        ),
        "checked_at": corporation.discord_bot_checked_at,
    }


def corporation_discord_settings(corporation: EveCorporation) -> dict:
    """The Settings tab's Discord section: the pasted link, the bot, and
    which of them the page shows."""
    if bot_invite_url(corporation):
        page_source = "bot"
    elif public_invite_url(corporation):
        page_source = "link"
    else:
        page_source = None
    return {
        **discord_settings(corporation),
        "bot": bot_settings(corporation),
        "page_source": page_source,
    }
