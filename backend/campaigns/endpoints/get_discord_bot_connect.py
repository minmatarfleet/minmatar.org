"""One endpoint: see the function below."""

from __future__ import annotations

import secrets

from django.shortcuts import get_object_or_404, redirect

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints.base import router
from campaigns.endpoints.discord_link_helpers import (
    PURPOSES,
    SESSION_KEY,
    _may_link,
)
from campaigns.models import Campaign
from campaigns.services import coordination


@router.get(
    "/{slug}/discord/bot/connect",
    response={
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: None,
    },
    include_in_schema=False,
)
def connect_bot(request, slug: str, purpose: str = "link", token: str = ""):
    """Start adding the bot to a server for this campaign (redirect)."""
    user = AuthBearer().authenticate(request, token) if token else None
    if user is None:
        return 401, {"detail": "Unauthorized"}
    campaign = get_object_or_404(Campaign, slug=slug)
    if purpose not in PURPOSES or not _may_link(user, campaign, purpose):
        return 403, {"detail": "Not authorised"}
    if not coordination.bot_configured():
        return 400, {"detail": "bot_not_configured"}
    state = secrets.token_urlsafe(24)
    request.session[SESSION_KEY] = {
        "state": state,
        "campaign_id": campaign.id,
        "user_id": user.id,
        "purpose": purpose,
    }
    request.session.modified = True
    return redirect(coordination.authorize_url(state))
