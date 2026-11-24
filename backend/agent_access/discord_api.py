"""The only Discord HTTP the agent tools make.

A small REST client with the bot token, deliberately separate from
`discord.client.DiscordClient`: it exposes just GET and the two POST/PUT
shapes the write tools need, makes one attempt with a short timeout and
returns a rate limit to the agent (with Retry-After) instead of backing
off inside a web request.
"""

import logging
from urllib.parse import quote

import requests
from django.conf import settings

from discord.client import BASE_URL, _assert_discord_http_allowed

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 8
_session = requests.Session()


class AgentDiscordError(Exception):
    """A Discord call failed; the message is safe to show the agent."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def snowflake(value, name: str) -> str:
    """A Discord id from tool input, or a refusal."""
    text = str(value or "").strip()
    if not text.isdigit() or not 15 <= len(text) <= 21:
        raise AgentDiscordError(f"{name} must be a Discord id (digits)")
    return text


def _request(method: str, path: str, **kwargs):
    _assert_discord_http_allowed()
    try:
        response = _session.request(
            method,
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bot {settings.DISCORD_BOT_TOKEN}"},
            timeout=TIMEOUT_SECONDS,
            **kwargs,
        )
    except requests.RequestException as e:
        logger.warning("Agent Discord %s %s failed: %s", method, path, e)
        raise AgentDiscordError("Discord did not answer; try again") from e
    if response.status_code == 429:
        retry = response.headers.get("Retry-After", "1")
        raise AgentDiscordError(
            f"Discord rate limit; retry after {retry}s", 429
        )
    if response.status_code in (403, 404):
        raise AgentDiscordError(
            "Not found, or the bot cannot see it", response.status_code
        )
    if response.status_code >= 400:
        detail = ""
        try:
            detail = str(response.json().get("message", ""))[:200]
        except ValueError:
            pass
        raise AgentDiscordError(
            f"Discord refused the request ({response.status_code}) {detail}",
            response.status_code,
        )
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def get(path: str, params: dict | None = None):
    return _request("GET", path, params=params)


def post_message(channel_id: str, payload: dict) -> dict:
    return _request("POST", f"/channels/{channel_id}/messages", json=payload)


def put_reaction(channel_id: str, message_id: str, emoji: str) -> None:
    encoded = quote(emoji, safe="")
    _request(
        "PUT",
        f"/channels/{channel_id}/messages/{message_id}/reactions/{encoded}/@me",
    )
