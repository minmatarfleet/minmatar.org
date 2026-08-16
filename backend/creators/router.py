"""Ninja router for creator account OAuth, Reddit username link, and public feed."""

from __future__ import annotations

import logging
import secrets
from typing import List, Optional

from django.contrib.auth.models import AnonymousUser, User
from django.shortcuts import redirect
from ninja import Router

from app.errors import create_error_id
from authentication import AuthBearer, AuthOptional
from creators.models import (
    CreatorAccount,
    CreatorItem,
    CreatorItemKind,
    CreatorProvider,
)
from creators.oauth import OAuthError, authorize_url
from creators.schemas import (
    CreatorAccountSchema,
    CreatorFeedItemSchema,
    CreatorLiveSchema,
    ErrorDetail,
    RedditUsernameRequest,
)
from creators.service import (
    disconnect_account,
    link_reddit_username,
    upsert_account_from_oauth,
)
from groups.helpers.feature_access import require_feature
from users.redirects import oauth_redirect

logger = logging.getLogger(__name__)

router = Router(tags=["Creators"])

OAUTH_PROVIDERS = {
    CreatorProvider.TWITCH,
    CreatorProvider.YOUTUBE,
}
ALL_PROVIDERS = OAUTH_PROVIDERS | {CreatorProvider.REDDIT}

SESSION_REDIRECT_KEY = "creators_oauth_redirect_url"
SESSION_STATE_KEY = "creators_oauth_state"
SESSION_PROVIDER_KEY = "creators_oauth_provider"
SESSION_USER_KEY = "creators_oauth_user_id"

FEATURE_CONNECT = "creators.connect"


def _iso(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _account_schema(account: CreatorAccount) -> CreatorAccountSchema:
    return CreatorAccountSchema(
        provider=account.provider,
        platform_user_id=account.platform_user_id,
        platform_username=account.platform_username,
        is_live=account.is_live,
        live_title=account.live_title or "",
        live_started_at=_iso(account.live_started_at),
        token_invalid=account.token_invalid,
        last_synced_at=_iso(account.last_synced_at),
    )


@router.get(
    "",
    response={
        200: List[CreatorAccountSchema],
        401: ErrorDetail,
        403: ErrorDetail,
    },
    auth=AuthBearer(),
    summary="List my connected creator accounts",
)
def list_my_accounts(request):
    denied = require_feature(request.user, FEATURE_CONNECT)
    if denied:
        return denied
    accounts = CreatorAccount.objects.filter(user=request.user).order_by(
        "provider"
    )
    return [_account_schema(a) for a in accounts]


@router.get(
    "/live",
    response=List[CreatorLiveSchema],
    summary="Public list of live Thinkspeak Twitch streams",
)
def list_live(request):
    accounts = (
        CreatorAccount.objects.filter(
            provider=CreatorProvider.TWITCH, is_live=True
        )
        .select_related("user")
        .order_by("-live_started_at")
    )
    results: list[CreatorLiveSchema] = []
    for account in accounts:
        login = account.platform_username or account.platform_user_id
        results.append(
            CreatorLiveSchema(
                user_id=account.user_id,
                provider=account.provider,
                platform_user_id=account.platform_user_id,
                platform_username=account.platform_username,
                title=account.live_title or "",
                url=f"https://www.twitch.tv/{login}",
                started_at=_iso(account.live_started_at),
            )
        )
    return results


@router.get(
    "/feed",
    response=List[CreatorFeedItemSchema],
    summary="Public ingested creator media feed",
)
def list_feed(
    request,
    provider: Optional[str] = None,
    limit: int = 25,
):
    limit = max(1, min(limit, 100))
    qs = (
        CreatorItem.objects.filter(
            kind__in=[
                CreatorItemKind.VIDEO,
                CreatorItemKind.VOD,
                CreatorItemKind.REDDIT_POST,
            ]
        )
        .select_related("account")
        .order_by("-published_at", "-id")
    )
    if provider:
        if provider not in ALL_PROVIDERS:
            return []
        qs = qs.filter(provider=provider)
    items = qs[:limit]
    return [
        CreatorFeedItemSchema(
            provider=item.provider,
            kind=item.kind,
            external_id=item.external_id,
            title=item.title,
            url=item.url,
            thumbnail_url=item.thumbnail_url,
            published_at=_iso(item.published_at),
            platform_username=item.account.platform_username,
            user_id=item.account.user_id,
        )
        for item in items
    ]


@router.put(
    "/reddit",
    response={
        200: CreatorAccountSchema,
        400: ErrorDetail,
        401: ErrorDetail,
        403: ErrorDetail,
    },
    auth=AuthBearer(),
    summary="Link a Reddit username for public-post polling",
)
def put_reddit_username(request, payload: RedditUsernameRequest):
    denied = require_feature(request.user, FEATURE_CONNECT)
    if denied:
        return denied
    try:
        account = link_reddit_username(request.user, payload.username)
    except ValueError:
        return 400, {"detail": "username_required"}
    return _account_schema(account)


@router.get(
    "/{provider}/connect",
    response={400: ErrorDetail, 401: ErrorDetail, 403: ErrorDetail},
    auth=AuthOptional(),
    summary="Start OAuth connect for Twitch or YouTube",
)
def connect_provider(
    request,
    provider: str,
    redirect_url: str,
    token: Optional[str] = None,
):
    user = request.user
    if (
        user is None
        or isinstance(user, AnonymousUser)
        or not getattr(user, "is_authenticated", False)
    ):
        if token:
            user = AuthBearer().authenticate(request, token)
        else:
            user = None
    if user is None:
        return 401, {"detail": "Unauthorized"}

    denied = require_feature(user, FEATURE_CONNECT)
    if denied:
        return denied
    if provider == CreatorProvider.REDDIT:
        return 400, {"detail": "use_put_reddit_username"}
    if provider not in OAUTH_PROVIDERS:
        return 400, {"detail": "unknown_provider"}
    if not redirect_url:
        return 400, {"detail": "redirect_url_required"}

    state = secrets.token_urlsafe(24)
    request.session[SESSION_REDIRECT_KEY] = redirect_url
    request.session[SESSION_STATE_KEY] = state
    request.session[SESSION_PROVIDER_KEY] = provider
    request.session[SESSION_USER_KEY] = user.id
    request.session.modified = True

    try:
        url = authorize_url(provider, state)
    except OAuthError as exc:
        return 400, {"detail": exc.code}
    return redirect(url)


@router.get(
    "/twitch/callback",
    include_in_schema=False,
)
def twitch_callback(
    request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    return _handle_callback(
        request,
        CreatorProvider.TWITCH,
        code=code,
        state=state,
        error=error,
    )


@router.get(
    "/youtube/callback",
    include_in_schema=False,
)
def youtube_callback(
    request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    return _handle_callback(
        request,
        CreatorProvider.YOUTUBE,
        code=code,
        state=state,
        error=error,
    )


def _handle_callback(
    request,
    expected_provider: str,
    *,
    code: Optional[str],
    state: Optional[str],
    error: Optional[str],
):
    redirect_url = request.session.pop(
        SESSION_REDIRECT_KEY, "https://my.minmatar.org/alliance/content/"
    )
    expected_state = request.session.pop(SESSION_STATE_KEY, None)
    session_provider = request.session.pop(SESSION_PROVIDER_KEY, None)
    user_id = request.session.pop(SESSION_USER_KEY, None)
    request.session.modified = True

    def fail(code_name: str):
        error_id = create_error_id()
        logger.info(
            "Creator OAuth failed provider=%s code=%s id=%s",
            expected_provider,
            code_name,
            error_id,
        )
        sep = "&" if "?" in redirect_url else "?"
        return oauth_redirect(
            f"{redirect_url}{sep}error={code_name}&id={error_id}"
        )

    if error:
        return fail("DENIED" if error == "access_denied" else "OAUTH_ERROR")
    if not code:
        return fail("DENIED")
    if not expected_state or state != expected_state:
        return fail("STATE_MISMATCH")
    if session_provider != expected_provider:
        return fail("PROVIDER_MISMATCH")
    if not user_id:
        return fail("SESSION_EXPIRED")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return fail("USER_MISSING")

    try:
        upsert_account_from_oauth(user, expected_provider, code)
    except OAuthError as exc:
        logger.warning(
            "Creator OAuth upsert failed: %s %s", exc.code, exc.message
        )
        return fail(exc.code.upper())
    except Exception:
        logger.exception("Creator OAuth upsert unexpected error")
        return fail("UPSERT_FAILED")

    sep = "&" if "?" in redirect_url else "?"
    return oauth_redirect(f"{redirect_url}{sep}connected={expected_provider}")


@router.delete(
    "/{provider}",
    response={200: dict, 401: ErrorDetail, 403: ErrorDetail, 404: ErrorDetail},
    auth=AuthBearer(),
    summary="Disconnect a creator provider",
)
def delete_provider(request, provider: str):
    denied = require_feature(request.user, FEATURE_CONNECT)
    if denied:
        return denied
    if provider not in ALL_PROVIDERS:
        return 404, {"detail": "unknown_provider"}
    if not disconnect_account(request.user, provider):
        return 404, {"detail": "not_connected"}
    return {"detail": "disconnected", "provider": provider}
