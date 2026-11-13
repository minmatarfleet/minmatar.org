"""GET /discord/bot/callback - Discord sends a tribe chief back.

A missing guild id, the alliance Discord, a Fishermen server, or a server
another corporation or tribe already uses is refused before the code is
exchanged. Exchanging the code adds the bot and can reset its managed role.
"""

import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User
from ninja import Router
from requests import RequestException

from app.errors import create_error_id
from app.links import site_url
from discord.client import DiscordClient, DiscordError
from discord.guild_roles import (
    MappingError,
    install_block_reason,
    link_tribe_guild,
    queue_snapshot,
)
from eveonline.tasks.corporations import release_corporation_discord_guild
from tribes.endpoints.tribe_discord.access import (
    can_manage_tribe_discord,
    load_tribe,
)
from tribes.endpoints.tribe_discord.get_tribe_discord_bot_connect import (
    SESSION_KEY,
)
from users.redirects import oauth_redirect

logger = logging.getLogger(__name__)

PATH = "/discord/bot/callback"
METHOD = "get"
ROUTE_SPEC = {
    "response": {302: None},
    "include_in_schema": False,
    "summary": "Discord bot install callback for a tribe",
}

router = Router(tags=["Tribes"])


def _tribe_url(tribe) -> str:
    if tribe is None:
        return site_url("/alliance/tribes/")
    return site_url(f"/alliance/tribes/{tribe.pk}/")


def _with_params(url: str, params: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{params}"


def get_tribe_discord_bot_callback(
    request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    guild_id: Optional[str] = None,
):
    pending = request.session.pop(SESSION_KEY, None) or {}
    request.session.modified = True
    tribe = (
        load_tribe(int(pending["tribe_id"]))
        if pending.get("tribe_id")
        else None
    )
    return_url = _tribe_url(tribe)

    def fail(reason: str):
        error_id = create_error_id()
        logger.info("Tribe Discord bot link failed: %s (%s)", reason, error_id)
        return oauth_redirect(
            _with_params(return_url, f"discord_bot_error={reason}")
        )

    if error:
        return fail("denied" if error == "access_denied" else "oauth_error")
    if not pending.get("state") or state != pending["state"]:
        return fail("session_expired")
    if not code or tribe is None:
        return fail("oauth_error")
    user = User.objects.filter(id=pending.get("user_id")).first()
    if user is None or not can_manage_tribe_discord(user, tribe):
        return fail("not_allowed")
    blocked = install_block_reason(guild_id, tribe_id=tribe.pk)
    if blocked:
        logger.warning(
            "Tribe %s tried to link Discord guild %s (%s)",
            tribe.pk,
            guild_id,
            blocked,
        )
        return fail(blocked)

    try:
        guild = DiscordClient().exchange_bot_code(
            code, settings.DISCORD_TRIBE_BOT_REDIRECT_URL
        )
    except (DiscordError, RequestException) as exc:
        logger.warning("Tribe Discord bot code exchange failed: %s", exc)
        return fail("exchange_failed")

    try:
        previous_id = link_tribe_guild(tribe, guild)
    except MappingError as exc:
        if exc.code == "alliance_server":
            logger.error(
                "Tribe %s added the bot to shared Discord guild %s; check "
                "the bot's role there",
                tribe.pk,
                guild.get("id"),
            )
        return fail(exc.code)

    queue_snapshot(tribe.discord_guild_id)
    if previous_id is not None:
        release_corporation_discord_guild.delay(previous_id, "")
    logger.info("Tribe %s linked Discord guild %s", tribe.pk, guild.get("id"))
    return oauth_redirect(_with_params(return_url, "discord_bot=connected"))


router.get(PATH, **ROUTE_SPEC)(get_tribe_discord_bot_callback)
