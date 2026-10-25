"""A corporation's one Discord server: its invite link, checked with Discord.

The CEO or a director pastes an invite. Discord tells us the server's name
and icon and whether the invite expires; one that expires is refused, since
the page would break when it does. A daily check marks invites that stopped
working, and the public page hides those (``public_invite_url``).
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ratelimit import RateLimitException
from requests import HTTPError, RequestException

from discord.client import DiscordClient
from eveonline.models import EveCorporation

logger = logging.getLogger(__name__)

INVITE_HOST = "discord.gg"
# discord.com/invite/<code> and the old discordapp.com links.
INVITE_PAGE_HOSTS = {
    "discord.com",
    "www.discord.com",
    "discordapp.com",
    "www.discordapp.com",
}
CODE_MAX = 64
ICON_URL = "https://cdn.discordapp.com/icons/{guild_id}/{icon}.png?size=64"

# Statuses in the settings response.
STATUS_OK = "ok"
STATUS_DEAD = "dead"
STATUS_UNCHECKED = "unchecked"

GUILD_NAME_MAX = EveCorporation._meta.get_field(
    "discord_invite_guild_name"
).max_length
ICON_MAX = EveCorporation._meta.get_field("discord_invite_icon").max_length


class DiscordInviteError(ValueError):
    """An invite that can't be used. `code` names the problem for the frontend."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class ResolvedInvite:
    guild_id: int | None
    guild_name: str
    icon: str
    expires_at: datetime | None


def parse_invite_code(value: str | None) -> str:
    """The invite code in discord.gg/<code> or discord.com/invite/<code>."""
    text = (value or "").strip()
    if not text:
        raise DiscordInviteError("url_required")
    if "://" not in text:
        text = f"https://{text}"
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host == INVITE_HOST and len(parts) == 1:
        code = parts[0]
    elif (
        host in INVITE_PAGE_HOSTS and len(parts) == 2 and parts[0] == "invite"
    ):
        code = parts[1]
    else:
        raise DiscordInviteError("not_discord_invite")
    if len(code) > CODE_MAX or not code.replace("-", "").isalnum():
        raise DiscordInviteError("not_discord_invite")
    return code


def invite_url(code: str) -> str:
    return f"https://{INVITE_HOST}/{code}"


def icon_url(guild_id: int | None, icon: str) -> str | None:
    if not guild_id or not icon:
        return None
    return ICON_URL.format(guild_id=guild_id, icon=icon)


def resolve_invite(code: str) -> ResolvedInvite | None:
    """What Discord says about the invite; None when Discord can't be asked.

    Raises DiscordInviteError("invite_not_found") for an expired or deleted
    invite, and "not_a_server" for a group DM invite.
    """
    try:
        data = DiscordClient().get_invite(code)
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise DiscordInviteError("invite_not_found") from e
        logger.warning("Discord invite %s lookup failed: %s", code, e)
        return None
    except (RequestException, RateLimitException) as e:
        logger.warning("Discord invite %s lookup failed: %s", code, e)
        return None
    guild = data.get("guild") or {}
    if not guild.get("id"):
        raise DiscordInviteError("not_a_server")
    expires_at = data.get("expires_at")
    return ResolvedInvite(
        guild_id=int(guild["id"]),
        guild_name=str(guild.get("name") or "")[:GUILD_NAME_MAX],
        icon=str(guild.get("icon") or "")[:ICON_MAX],
        expires_at=parse_datetime(expires_at) if expires_at else None,
    )


def check_invite(url: str | None) -> tuple[str, ResolvedInvite | None]:
    """(code, invite) for a link the corp may save. Refuses invites that
    expire; a None invite means Discord couldn't be asked, so it is saved
    unchecked and the daily check catches up."""
    code = parse_invite_code(url)
    resolved = resolve_invite(code)
    if resolved is not None and resolved.expires_at is not None:
        raise DiscordInviteError("invite_expires")
    return code, resolved


def invite_preview(url: str | None) -> dict:
    code, resolved = check_invite(url)
    return {
        "invite_url": invite_url(code),
        "checked": resolved is not None,
        "guild_name": resolved.guild_name if resolved else None,
        "icon_url": (
            icon_url(resolved.guild_id, resolved.icon) if resolved else None
        ),
    }


def _apply(corporation: EveCorporation, resolved: ResolvedInvite) -> None:
    corporation.discord_invite_status = EveCorporation.DISCORD_INVITE_OK
    corporation.discord_invite_guild_id = resolved.guild_id
    corporation.discord_invite_guild_name = resolved.guild_name
    corporation.discord_invite_icon = resolved.icon
    corporation.discord_invite_checked_at = timezone.now()


INVITE_FIELDS = [
    "discord_invite_url",
    "discord_invite_status",
    "discord_invite_guild_id",
    "discord_invite_guild_name",
    "discord_invite_icon",
    "discord_invite_checked_at",
]


def save_discord_invite(corporation: EveCorporation, url: str | None) -> None:
    code, resolved = check_invite(url)
    corporation.discord_invite_url = invite_url(code)
    if resolved is None:
        corporation.discord_invite_status = ""
        corporation.discord_invite_guild_id = None
        corporation.discord_invite_guild_name = ""
        corporation.discord_invite_icon = ""
        corporation.discord_invite_checked_at = None
    else:
        _apply(corporation, resolved)
    corporation.save(update_fields=INVITE_FIELDS)


def remove_discord_invite(corporation: EveCorporation) -> None:
    corporation.discord_invite_url = ""
    corporation.discord_invite_status = ""
    corporation.discord_invite_guild_id = None
    corporation.discord_invite_guild_name = ""
    corporation.discord_invite_icon = ""
    corporation.discord_invite_checked_at = None
    corporation.save(update_fields=INVITE_FIELDS)


def recheck_discord_invite(corporation: EveCorporation) -> str | None:
    """Ask Discord again. Returns the new status, or None when unchanged
    because there's no link or Discord couldn't be asked."""
    if not corporation.discord_invite_url:
        return None
    try:
        code = parse_invite_code(corporation.discord_invite_url)
        resolved = resolve_invite(code)
    except DiscordInviteError:
        corporation.discord_invite_status = EveCorporation.DISCORD_INVITE_DEAD
        corporation.discord_invite_checked_at = timezone.now()
        corporation.save(update_fields=INVITE_FIELDS)
        return corporation.discord_invite_status
    if resolved is None:
        return None
    _apply(corporation, resolved)
    corporation.save(update_fields=INVITE_FIELDS)
    return corporation.discord_invite_status


def invite_status(corporation: EveCorporation) -> str:
    if corporation.discord_invite_status == EveCorporation.DISCORD_INVITE_DEAD:
        return STATUS_DEAD
    if corporation.discord_invite_status == EveCorporation.DISCORD_INVITE_OK:
        return STATUS_OK
    return STATUS_UNCHECKED


def public_invite_url(corporation: EveCorporation) -> str | None:
    """The link visitors get: none while it is known to be dead."""
    if not corporation.discord_invite_url:
        return None
    if invite_status(corporation) == STATUS_DEAD:
        return None
    return corporation.discord_invite_url


def discord_settings(corporation: EveCorporation) -> dict:
    exists = bool(corporation.discord_invite_url)
    return {
        "corporation_id": corporation.corporation_id,
        "exists": exists,
        "invite_url": corporation.discord_invite_url or None,
        "status": invite_status(corporation) if exists else None,
        "guild_name": corporation.discord_invite_guild_name or None,
        "icon_url": icon_url(
            corporation.discord_invite_guild_id,
            corporation.discord_invite_icon,
        ),
        "checked_at": corporation.discord_invite_checked_at,
    }
