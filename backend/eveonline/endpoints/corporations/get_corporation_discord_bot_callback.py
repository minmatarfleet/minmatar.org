"""GET /corporations/discord/bot/callback - Discord sends the person back.

The code exchange adds the bot and says which server that was. A missing
guild id, the alliance Discord, a Fishermen server, or a server another
corporation or tribe already uses is refused before the exchange, because
exchanging the code can reset the bot's managed role.
"""

import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User
from requests import RequestException

from app.errors import create_error_id
from app.links import site_url
from discord.client import DiscordClient, DiscordError
from discord.guild_roles import install_block_reason
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
    blocked = install_block_reason(
        guild_id, corporation_id=corporation.corporation_id
    )
    if blocked:
        logger.warning(
            "Corp %s tried to link Discord guild %s (%s)",
            corporation.corporation_id,
            guild_id,
            blocked,
        )
        return fail(blocked)

    try:
        guild = DiscordClient().exchange_bot_code(
            code, settings.DISCORD_CORP_BOT_REDIRECT_URL
        )
    except (DiscordError, RequestException) as e:
        logger.warning("Corp Discord bot code exchange failed: %s", e)
        return fail("exchange_failed")

    try:
        previous = link_guild(corporation, guild, user)
    except DiscordBotError as e:
        if e.code == "alliance_server":
            logger.error(
                "Corp %s added the bot to shared Discord guild %s; check "
                "the bot's role there",
                corporation.corporation_id,
                guild.get("id"),
            )
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
