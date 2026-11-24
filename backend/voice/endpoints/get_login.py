"""GET /api/voice/login: EVE sign-in for /voice, public info only."""

import re

from django.conf import settings
from esi.views import sso_redirect

from users.redirects import oauth_redirect, safe_login_redirect_url
from voice.endpoints.base import router
from voice.views import (
    SESSION_KEY,
    STATE_SESSION_KEY,
    default_voice_login_url,
)

STATE_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,128}")


@router.get(
    "/login",
    summary="Sign in to fleet voice with EVE (public info only)",
    description=(
        "Redirects to EVE SSO asking only for publicData. Afterwards the "
        "browser lands on redirect_url with ?token=<voice session token>"
        "&state=<state>. The website sets state in a cookie before sending "
        "the browser here, and only keeps a token whose state matches."
    ),
    response={302: None},
)
def get_login(request, redirect_url: str = "", state: str = ""):
    redirect_url = safe_login_redirect_url(
        redirect_url, default_voice_login_url()
    )
    if not settings.ESI_SSO_CLIENT_ID or not settings.ESI_SSO_CALLBACK_URL:
        return oauth_redirect(f"{redirect_url}?error=NOT_CONFIGURED")
    request.session[SESSION_KEY] = redirect_url
    request.session[STATE_SESSION_KEY] = (
        state if STATE_PATTERN.fullmatch(state) else ""
    )
    return sso_redirect(
        request, scopes=["publicData"], return_to="voice_sso_complete"
    )
