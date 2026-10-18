"""Reddit authorization-code OAuth for linking a user's own account."""

import hashlib
import logging
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REVOKE_URL = "https://www.reddit.com/api/v1/revoke_token"
ME_URL = "https://oauth.reddit.com/api/v1/me"

# identity: read the username; submit: post; flair: list and set link flair.
SCOPES = ("identity", "submit", "flair")

ACCESS_TOKEN_CACHE_PREFIX = "reddit:access-token:"
# Reddit access tokens last an hour (expires_in). Drop ours five minutes
# early so a token is never used right at its expiry.
ACCESS_TOKEN_EXPIRY_MARGIN_SECONDS = 300
DEFAULT_ACCESS_TOKEN_SECONDS = 3600


class RedditOAuthError(Exception):
    """Reddit OAuth failure. `code` is a short machine-readable reason."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


def user_agent() -> str:
    return "minmatar.org " + settings.ENV


def _client_auth():
    return requests.auth.HTTPBasicAuth(
        settings.REDDIT_CLIENT_ID, settings.REDDIT_SECRET
    )


def authorize_url(state: str) -> str:
    params = {
        "client_id": settings.REDDIT_CLIENT_ID,
        "response_type": "code",
        "state": state,
        "redirect_uri": settings.REDDIT_REDIRECT_URL,
        "duration": "permanent",
        "scope": " ".join(SCOPES),
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _token_request(data: dict) -> dict:
    response = requests.post(
        TOKEN_URL,
        auth=_client_auth(),
        data=data,
        headers={"User-Agent": user_agent()},
        timeout=15,
    )
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400 or "error" in body:
        logger.warning(
            "Reddit token request (%s) failed: %s %s",
            data.get("grant_type"),
            response.status_code,
            body.get("error") or response.text[:200],
        )
        code = (
            "invalid_grant"
            if body.get("error") == "invalid_grant"
            or response.status_code in (400, 401)
            else "token_request_failed"
        )
        raise RedditOAuthError(code)
    if not body.get("access_token"):
        raise RedditOAuthError("token_missing")
    return body


def _access_token_key(grant: str, identity: str) -> str:
    """Cache key for one grant. The identity (username or refresh token)
    is hashed so no credential appears in a cache key."""
    digest = hashlib.sha256(
        f"{settings.REDDIT_CLIENT_ID}:{grant}:{identity}".encode()
    ).hexdigest()
    return ACCESS_TOKEN_CACHE_PREFIX + digest


def _cache_get(key: str):
    try:
        return cache.get(key)
    except Exception:  # pragma: no cover - cache backend down
        logger.warning("Reddit token cache unavailable", exc_info=True)
        return None


def _cache_set(key: str, value: str, seconds: int) -> None:
    try:
        cache.set(key, value, seconds)
    except Exception:  # pragma: no cover
        logger.warning("Reddit token cache unavailable", exc_info=True)


def _cache_seconds(body: dict) -> int:
    try:
        lifetime = int(body.get("expires_in") or DEFAULT_ACCESS_TOKEN_SECONDS)
    except (TypeError, ValueError):
        lifetime = DEFAULT_ACCESS_TOKEN_SECONDS
    return lifetime - ACCESS_TOKEN_EXPIRY_MARGIN_SECONDS


def _cached_access_token(grant: str, identity: str, data: dict) -> str:
    """An access token for this grant, from the cache until near expiry.

    Two workers that miss at once both ask Reddit and the later write
    wins; both tokens are valid, so no lock is needed.
    """
    key = _access_token_key(grant, identity)
    token = _cache_get(key)
    if token:
        return token
    body = _token_request(data)
    seconds = _cache_seconds(body)
    if seconds > 0:
        _cache_set(key, body["access_token"], seconds)
    return body["access_token"]


def forget_access_token(grant: str, identity: str) -> None:
    """Drop a cached token Reddit has rejected (e.g. after a 401)."""
    try:
        cache.delete(_access_token_key(grant, identity))
    except Exception:  # pragma: no cover
        logger.warning("Reddit token cache unavailable", exc_info=True)


def password_access_token(username: str, password: str) -> str:
    """The alliance account's access token (password grant), cached."""
    return _cached_access_token(
        "password",
        username,
        {
            "grant_type": "password",
            "username": username,
            "password": password,
        },
    )


def exchange_code(code: str) -> dict:
    """Swap an authorization code for access and refresh tokens."""
    return _token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.REDDIT_REDIRECT_URL,
        }
    )


def refresh_access_token(refresh_token: str) -> str:
    """A one-hour access token from a stored refresh token, cached."""
    if not refresh_token:
        raise RedditOAuthError("invalid_grant")
    return _cached_access_token(
        "refresh_token",
        refresh_token,
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
    )


def fetch_username(access_token: str) -> str:
    response = requests.get(
        ME_URL,
        headers={
            "Authorization": "bearer " + access_token,
            "User-Agent": user_agent(),
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise RedditOAuthError("identity_failed")
    name = response.json().get("name")
    if not name:
        raise RedditOAuthError("identity_failed")
    return name


def revoke_refresh_token(refresh_token: str) -> None:
    """Best effort: tell Reddit to drop the grant when a user disconnects."""
    if not refresh_token:
        return
    try:
        requests.post(
            REVOKE_URL,
            auth=_client_auth(),
            data={
                "token": refresh_token,
                "token_type_hint": "refresh_token",
            },
            headers={"User-Agent": user_agent()},
            timeout=10,
        )
    except requests.RequestException:
        logger.warning("Failed to revoke Reddit refresh token", exc_info=True)
