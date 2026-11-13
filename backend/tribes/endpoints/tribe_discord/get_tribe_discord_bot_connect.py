"""GET /{tribe_id}/discord/bot/connect - add the bot to the tribe's server."""

import secrets

from django.conf import settings
from django.shortcuts import redirect
from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.guild_roles import tribe_bot_configured
from eveonline.helpers.corporations.discord_bot import authorize_url
from tribes.endpoints.tribe_discord.access import (
    can_manage_tribe_discord,
    load_tribe,
)

SESSION_KEY = "tribe_discord_bot"

PATH = "/{tribe_id}/discord/bot/connect"
METHOD = "get"
ROUTE_SPEC = {
    "response": {
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "include_in_schema": False,
    "summary": "Start adding the bot to the tribe's Discord (redirect)",
}

router = Router(tags=["Tribes"])


def get_tribe_discord_bot_connect(request, tribe_id: int, token: str = ""):
    user = AuthBearer().authenticate(request, token) if token else None
    if user is None:
        return 401, ErrorResponse(detail="Unauthorized")
    tribe = load_tribe(tribe_id)
    if tribe is None:
        return 404, ErrorResponse(detail="Tribe not found")
    if not can_manage_tribe_discord(user, tribe):
        return 403, ErrorResponse(detail="Not authorised")
    if not tribe_bot_configured():
        return 400, ErrorResponse(detail="bot_not_configured")

    state = secrets.token_urlsafe(24)
    request.session[SESSION_KEY] = {
        "state": state,
        "tribe_id": tribe.pk,
        "user_id": user.id,
    }
    request.session.modified = True
    return redirect(
        authorize_url(state, settings.DISCORD_TRIBE_BOT_REDIRECT_URL)
    )


router.get(PATH, **ROUTE_SPEC)(get_tribe_discord_bot_connect)
