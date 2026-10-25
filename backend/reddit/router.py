"""Reddit account linking and the CEO's corporation post settings."""

import logging
import secrets
from typing import Optional
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import redirect
from ninja import Router

from app.errors import ErrorResponse, create_error_id
from authentication import AuthBearer
from eveonline.helpers.corporations.permissions import (
    can_edit_corporation_settings,
)
from eveonline.helpers.corporations.profile import load_corporation
from reddit.corporation_posts import (
    PostSettingsError,
    post_settings,
    save_post_settings,
)
from reddit.models import RedditAccount
from reddit.oauth import (
    RedditOAuthError,
    authorize_url,
    exchange_code,
    fetch_username,
    revoke_refresh_token,
)
from reddit.schemas import (
    CorporationRedditPost,
    CorporationRedditPostUpdate,
    PostSettingsErrorResponse,
)
from users.redirects import oauth_redirect

logger = logging.getLogger(__name__)

router = Router(tags=["Reddit"])

SESSION_STATE_KEY = "reddit_oauth_state"
SESSION_REDIRECT_KEY = "reddit_oauth_redirect_url"
SESSION_USER_KEY = "reddit_oauth_user_id"


def _settings_corporation(request, corporation_id: int):
    """(corporation, None) for the CEO or a director, else (None, error)."""
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return None, (404, ErrorResponse(detail="Corporation not found"))
    if not can_edit_corporation_settings(request.user, corporation):
        return None, (
            403,
            ErrorResponse(detail="Only the CEO and directors can do this"),
        )
    return corporation, None


@router.get(
    "/corporations/{corporation_id}/post",
    response={
        200: CorporationRedditPost,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="The corporation's Reddit post template (CEO and directors)",
)
def get_corporation_post(request, corporation_id: int):
    corporation, error = _settings_corporation(request, corporation_id)
    if error:
        return error
    return post_settings(corporation, request.user)


@router.put(
    "/corporations/{corporation_id}/post",
    response={
        200: CorporationRedditPost,
        400: PostSettingsErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Edit the corporation's Reddit post, pause it, or change how it is sent (CEO and directors)",
)
def put_corporation_post(
    request, corporation_id: int, payload: CorporationRedditPostUpdate
):
    corporation, error = _settings_corporation(request, corporation_id)
    if error:
        return error
    try:
        save_post_settings(
            corporation,
            payload.title,
            payload.content,
            payload.delivery_method,
            payload.paused,
            user=request.user,
        )
    except PostSettingsError as e:
        return 400, {"detail": e.code, "problems": e.problems}
    return post_settings(corporation, request.user)


def _allowed_return_url(url: str) -> bool:
    """Only send people back to this site's own frontend."""
    target = urlparse(url or "")
    site = urlparse(settings.WEB_LINK_URL)
    return target.scheme in ("http", "https") and (
        (target.scheme, target.netloc) == (site.scheme, site.netloc)
    )


@router.get(
    "/connect",
    response={400: ErrorResponse, 401: ErrorResponse},
    summary="Start linking a Reddit account (browser redirect)",
)
def connect(request, redirect_url: str, token: str = ""):
    # A browser navigation carries no Authorization header, so the frontend
    # passes the JWT as a query param (same as the creators connect flow).
    user = AuthBearer().authenticate(request, token) if token else None
    if user is None:
        return 401, ErrorResponse(detail="Unauthorized")
    if not _allowed_return_url(redirect_url):
        return 400, ErrorResponse(detail="redirect_url_not_allowed")
    if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_REDIRECT_URL:
        return 400, ErrorResponse(detail="reddit_not_configured")

    state = secrets.token_urlsafe(24)
    request.session[SESSION_STATE_KEY] = state
    request.session[SESSION_REDIRECT_KEY] = redirect_url
    request.session[SESSION_USER_KEY] = user.id
    request.session.modified = True
    return redirect(authorize_url(state))


def _with_params(url: str, params: str) -> str:
    """Add query params before any #fragment."""
    base, hash_mark, fragment = url.partition("#")
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{params}{hash_mark}{fragment}"


@router.get("/callback", include_in_schema=False)
def callback(
    request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    redirect_url = request.session.pop(
        SESSION_REDIRECT_KEY, settings.WEB_LINK_URL
    )
    expected_state = request.session.pop(SESSION_STATE_KEY, None)
    user_id = request.session.pop(SESSION_USER_KEY, None)
    request.session.modified = True

    def fail(reason: str):
        error_id = create_error_id()
        logger.info("Reddit link failed: %s (%s)", reason, error_id)
        return oauth_redirect(
            _with_params(redirect_url, f"reddit_error={reason}&id={error_id}")
        )

    if error:
        return fail("denied" if error == "access_denied" else "oauth_error")
    if not expected_state or state != expected_state:
        return fail("state_mismatch")
    if not code or not user_id:
        return fail("session_expired")
    user = User.objects.filter(id=user_id).first()
    if user is None:
        return fail("session_expired")

    try:
        tokens = exchange_code(code)
        username = fetch_username(tokens["access_token"])
    except RedditOAuthError as e:
        return fail(e.code)
    if not tokens.get("refresh_token"):
        return fail("no_refresh_token")

    RedditAccount.objects.update_or_create(
        user=user,
        defaults={
            "reddit_username": username,
            "refresh_token": tokens["refresh_token"],
            "scopes": (tokens.get("scope") or "").split(),
            "token_invalid": False,
        },
    )
    logger.info("Linked Reddit account u/%s to %s", username, user)
    return oauth_redirect(_with_params(redirect_url, "reddit=connected"))


@router.delete(
    "/account",
    response={200: dict, 404: ErrorResponse},
    auth=AuthBearer(),
    summary="Unlink my Reddit account",
)
def disconnect(request):
    account = RedditAccount.objects.filter(user=request.user).first()
    if account is None:
        return 404, ErrorResponse(detail="not_connected")
    revoke_refresh_token(account.refresh_token)
    account.delete()
    return {"detail": "disconnected"}
