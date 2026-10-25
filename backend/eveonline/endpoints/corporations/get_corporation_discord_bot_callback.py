"""GET /corporations/discord/bot/callback - Discord sends the person back.

Discord has added the bot to the server they picked. The code exchange says
which server that was; the guild_id on this URL is only used to turn away
the alliance and tribe servers before the exchange.
"""

import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User
from requests import RequestException

from app.errors import create_error_id
from app.links import site_url
from discord.client import DiscordClient, DiscordError
from discord.models import DiscordGuild
from eveonline.endpoints.corporations.get_corporation_discord_bot_connect import (
    SESSION_KEY,
)
from eveonline.helpers.corporations.discord_bot import (
    DiscordBotError,
    link_guild,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation
from eveonline.helpers.corporations.slugs import corporation_slug
from eveonline.tasks.corporations import (
    refresh_corporation_discord_bot,
    release_corporation_discord_guild,
)
from users.redirects import oauth_redirect

logger = logging.getLogger(__name__)

PATH = "corporations/discord/bot/callback"
METHOD = "get"
ROUTE_SPEC = {
    "response": {302: None},
    "include_in_schema": False,
    "summary": "Discord bot install callback for a corporation",
}


def _settings_url(corporation) -> str:
    if corporation is None:
        return site_url("/alliance/corporations/")
    slug = corporation_slug(corporation.name)
    return site_url(f"/alliance/corporations/{slug}/")


def _with_params(url: str, params: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{params}#settings"


def _shared_server(guild_id: str | None) -> bool:
    """The alliance Discord or a tribe's server. Linking one would point a
    corporation page at it, and adding the bot again could change the
    bot's role there."""
    try:
        guild_id = int(guild_id or 0)
    except ValueError:
        return False
    if not guild_id:
        return False
    if guild_id == int(settings.DISCORD_GUILD_ID):
        return True
    return DiscordGuild.objects.filter(
        guild_id=guild_id, tribe_group_bindings__isnull=False
    ).exists()


def get_corporation_discord_bot_callback(
    request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    guild_id: Optional[str] = None,
):
    pending = request.session.pop(SESSION_KEY, None) or {}
    request.session.modified = True
    corporation = (
        load_corporation(int(pending["corporation_id"]))
        if pending.get("corporation_id")
        else None
    )
    return_url = _settings_url(corporation)

    def fail(reason: str):
        error_id = create_error_id()
        logger.info("Corp Discord bot link failed: %s (%s)", reason, error_id)
        return oauth_redirect(
            _with_params(return_url, f"discord_bot_error={reason}")
        )

    if error:
        return fail("denied" if error == "access_denied" else "oauth_error")
    if not pending.get("state") or state != pending["state"]:
        return fail("session_expired")
    if not code or corporation is None:
        return fail("oauth_error")
    user = User.objects.filter(id=pending.get("user_id")).first()
    if user is None or not can_edit_corporation_settings(user, corporation):
        return fail("not_allowed")
    if _shared_server(guild_id):
        logger.warning(
            "Corp %s tried to link shared Discord guild %s",
            corporation.corporation_id,
            guild_id,
        )
        return fail("alliance_server")

    try:
        guild = DiscordClient().exchange_bot_code(
            code, settings.DISCORD_CORP_BOT_REDIRECT_URL
        )
    except (DiscordError, RequestException) as e:
        logger.warning("Corp Discord bot code exchange failed: %s", e)
        return fail("exchange_failed")
    if _shared_server(guild.get("id")):
        logger.error(
            "Corp %s added the bot to shared Discord guild %s; check the "
            "bot's role there",
            corporation.corporation_id,
            guild.get("id"),
        )
        return fail("alliance_server")

    try:
        previous = link_guild(corporation, guild, user)
    except DiscordBotError as e:
        return fail(e.code)
    refresh_corporation_discord_bot.delay(corporation.corporation_id)
    if previous is not None:
        release_corporation_discord_guild.delay(
            previous.guild_id, previous.invite_code
        )
    logger.info(
        "Corp %s linked Discord guild %s",
        corporation.corporation_id,
        guild.get("id"),
    )
    return oauth_redirect(_with_params(return_url, "discord_bot=connected"))
