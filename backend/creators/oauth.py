"""OAuth authorize / token exchange / refresh / revoke for creator providers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from creators.models import CreatorProvider

logger = logging.getLogger(__name__)

TWITCH_AUTHORIZE_URL = "https://id.twitch.tv/oauth2/authorize"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_REVOKE_URL = "https://id.twitch.tv/oauth2/revoke"

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

TWITCH_SCOPES = ("user:read:email",)
YOUTUBE_SCOPES = ("https://www.googleapis.com/auth/youtube.readonly",)


@dataclass
class TokenPayload:
    access_token: str
    refresh_token: str
    expires_at: Any  # datetime | None
    scopes: list[str]
    raw: dict[str, Any]


class OAuthError(Exception):
    """Provider OAuth failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def provider_redirect_url(provider: str) -> str:
    if provider == CreatorProvider.TWITCH:
        return settings.TWITCH_REDIRECT_URL
    if provider == CreatorProvider.YOUTUBE:
        return settings.YOUTUBE_REDIRECT_URL
    raise OAuthError("unknown_provider", f"Unknown provider: {provider}")


def authorize_url(provider: str, state: str) -> str:
    if provider == CreatorProvider.TWITCH:
        params = {
            "client_id": settings.TWITCH_CLIENT_ID,
            "redirect_uri": settings.TWITCH_REDIRECT_URL,
            "response_type": "code",
            "scope": " ".join(TWITCH_SCOPES),
            "state": state,
            "force_verify": "true",
        }
        return f"{TWITCH_AUTHORIZE_URL}?{urlencode(params)}"

    if provider == CreatorProvider.YOUTUBE:
        params = {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "redirect_uri": settings.YOUTUBE_REDIRECT_URL,
            "response_type": "code",
            "scope": " ".join(YOUTUBE_SCOPES),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"

    raise OAuthError("unknown_provider", f"Unknown provider: {provider}")


def _parse_token_response(
    data: dict[str, Any], *, default_scopes: tuple[str, ...]
) -> TokenPayload:
    access = data.get("access_token")
    if not access:
        raise OAuthError("token_missing", "No access_token in response")
    expires_in = data.get("expires_in")
    expires_at = None
    if expires_in is not None:
        try:
            expires_at = timezone.now() + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            expires_at = None
    scope_raw = data.get("scope")
    if isinstance(scope_raw, str):
        scopes = [s for s in scope_raw.replace(",", " ").split() if s]
    elif isinstance(scope_raw, list):
        scopes = [str(s) for s in scope_raw]
    else:
        scopes = list(default_scopes)
    return TokenPayload(
        access_token=access,
        refresh_token=data.get("refresh_token") or "",
        expires_at=expires_at,
        scopes=scopes,
        raw=data,
    )


def exchange_code(provider: str, code: str) -> TokenPayload:
    redirect_uri = provider_redirect_url(provider)

    if provider == CreatorProvider.TWITCH:
        response = requests.post(
            TWITCH_TOKEN_URL,
            data={
                "client_id": settings.TWITCH_CLIENT_ID,
                "client_secret": settings.TWITCH_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=15,
        )
        if response.status_code >= 400:
            logger.warning(
                "Twitch code exchange failed: %s %s",
                response.status_code,
                response.text[:200],
            )
            raise OAuthError("exchange_failed", "Twitch token exchange failed")
        return _parse_token_response(
            response.json(), default_scopes=TWITCH_SCOPES
        )

    if provider == CreatorProvider.YOUTUBE:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=15,
        )
        if response.status_code >= 400:
            logger.warning(
                "YouTube code exchange failed: %s %s",
                response.status_code,
                response.text[:200],
            )
            raise OAuthError(
                "exchange_failed", "YouTube token exchange failed"
            )
        return _parse_token_response(
            response.json(), default_scopes=YOUTUBE_SCOPES
        )

    raise OAuthError("unknown_provider", f"Unknown provider: {provider}")


def refresh_access_token(provider: str, refresh_token: str) -> TokenPayload:
    if not refresh_token:
        raise OAuthError("no_refresh", "No refresh token")

    if provider == CreatorProvider.TWITCH:
        response = requests.post(
            TWITCH_TOKEN_URL,
            data={
                "client_id": settings.TWITCH_CLIENT_ID,
                "client_secret": settings.TWITCH_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        if response.status_code >= 400:
            raise OAuthError("refresh_failed", "Twitch refresh failed")
        payload = _parse_token_response(
            response.json(), default_scopes=TWITCH_SCOPES
        )
        if not payload.refresh_token:
            payload.refresh_token = refresh_token
        return payload

    if provider == CreatorProvider.YOUTUBE:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        if response.status_code >= 400:
            raise OAuthError("refresh_failed", "YouTube refresh failed")
        payload = _parse_token_response(
            response.json(), default_scopes=YOUTUBE_SCOPES
        )
        if not payload.refresh_token:
            payload.refresh_token = refresh_token
        return payload

    raise OAuthError("unknown_provider", f"Unknown provider: {provider}")


def revoke_token(provider: str, token: str) -> None:
    if not token:
        return
    try:
        if provider == CreatorProvider.TWITCH:
            requests.post(
                TWITCH_REVOKE_URL,
                data={
                    "client_id": settings.TWITCH_CLIENT_ID,
                    "token": token,
                },
                timeout=10,
            )
        elif provider == CreatorProvider.YOUTUBE:
            requests.post(
                GOOGLE_REVOKE_URL,
                params={"token": token},
                timeout=10,
            )
    except requests.RequestException:
        logger.exception("Failed to revoke %s token", provider)


def twitch_app_access_token() -> str | None:
    """Client-credentials token for public Helix reads (live poll)."""
    response = requests.post(
        TWITCH_TOKEN_URL,
        data={
            "client_id": settings.TWITCH_CLIENT_ID,
            "client_secret": settings.TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=15,
    )
    if response.status_code >= 400:
        logger.warning(
            "Twitch app token failed: %s %s",
            response.status_code,
            response.text[:200],
        )
        return None
    return response.json().get("access_token")
