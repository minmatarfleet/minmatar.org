"""GET /corporations/{corporation_id}/discord/bot/connect - add the bot.

A browser navigation from the Settings tab (so the JWT comes as a query
param, as in the Reddit connect flow). Sends the CEO or director to
Discord's page for adding the bot to a server they manage.
"""

import secrets

from django.shortcuts import redirect

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.corporations.discord_bot import (
    authorize_url,
    bot_configured,
)
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation

# The callback checks Discord's state against this, so a callback only
# links a server for the browser that started it.
SESSION_KEY = "corporation_discord_bot"

PATH = "corporations/{corporation_id}/discord/bot/connect"
METHOD = "get"
ROUTE_SPEC = {
    "response": {
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "include_in_schema": False,
    "summary": "Start adding the bot to the corporation's Discord (redirect)",
}


def get_corporation_discord_bot_connect(
    request, corporation_id: int, token: str = ""
):
    user = AuthBearer().authenticate(request, token) if token else None
    if user is None:
        return 401, ErrorResponse(detail="Unauthorized")
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_edit_corporation_settings(user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    if not bot_configured():
        return 400, ErrorResponse(detail="bot_not_configured")

    state = secrets.token_urlsafe(24)
    request.session[SESSION_KEY] = {
        "state": state,
        "corporation_id": corporation.corporation_id,
        "user_id": user.id,
    }
    request.session.modified = True
    return redirect(authorize_url(state))
