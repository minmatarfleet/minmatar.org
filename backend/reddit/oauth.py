"""Reddit authorization-code OAuth for linking a user's own account."""

import logging
from urllib.parse import urlencode

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REVOKE_URL = "https://www.reddit.com/api/v1/revoke_token"
ME_URL = "https://oauth.reddit.com/api/v1/me"

# identity: read the username; submit: post; flair: list and set link flair.
SCOPES = ("identity", "submit", "flair")


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
    """A fresh one-hour access token from a stored refresh token."""
    if not refresh_token:
        raise RedditOAuthError("invalid_grant")
    return _token_request(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}
    )["access_token"]


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
