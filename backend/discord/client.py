"""Client wrapper for interacting with Discord API"""

import logging

import requests
from backoff import expo, on_exception
from django.conf import settings
from ratelimit import RateLimitException, limits
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from app.errors import create_error_id

from .core import DISCORD_NICKNAME_MAX_LENGTH

logger = logging.getLogger(__name__)

GUILD_ID = settings.DISCORD_GUILD_ID
BASE_URL = "https://discord.com/api/v9"

# Default giveup_log_level is ERROR and creates Sentry issues (CELERY-JT).
_DISCORD_RATE_LIMIT_RETRY = {
    "max_tries": 8,
    "giveup_log_level": logging.WARNING,
}


retry_strategy = Retry(
    total=5,
    status_forcelist=[429, 500, 502, 503, 504],
    backoff_factor=1,
)

s = requests.Session()
s.mount("https://", HTTPAdapter(max_retries=retry_strategy))


class DiscordError(Exception):
    """An error calling the Discord API"""

    status_code: int
    description: str
    code: str
    id: str

    @classmethod
    def for_response(
        cls, description: str, code: str, response: requests.Response
    ):
        e = cls(description)
        e.description = description
        e.status_code = response.status_code
        e.code = code
        e.id = create_error_id()
        return e


def _assert_discord_http_allowed() -> None:
    """
    Block live Discord HTTP during Django unit tests unless explicitly enabled.

    settings_test sets TESTING=True and blank credentials. Live verification
    uses app.settings (TESTING false) or ALLOW_LIVE_DISCORD_IN_TESTS=True.
    """
    if not getattr(settings, "TESTING", False):
        return
    if getattr(settings, "ALLOW_LIVE_DISCORD_IN_TESTS", False):
        return
    raise RuntimeError(
        "Refusing live Discord HTTP during unit tests. Mock "
        "discord.signals.discord / DiscordClient, or set "
        "ALLOW_LIVE_DISCORD_IN_TESTS=True only for intentional live runs."
    )


def _raise_discord_rate_limit(response: requests.Response) -> None:
    """Raise RateLimitException with Discord Retry-After for backoff retries."""
    raw = response.headers.get("Retry-After", "1")
    try:
        period_remaining = float(raw)
    except (TypeError, ValueError):
        period_remaining = 1.0
    raise RateLimitException("Discord API rate limited", period_remaining)


class DiscordBaseClient:
    """Base Discord API Client"""

    def __init__(self):
        self.access_token = settings.DISCORD_BOT_TOKEN
        self.guild_id = GUILD_ID
        self.session = s

    @limits(calls=5, period=1)
    def check_ratelimit(self):
        pass

    @on_exception(expo, RateLimitException, **_DISCORD_RATE_LIMIT_RETRY)
    def post(self, *args, **kwargs):
        """Post a resource using REST API"""
        _assert_discord_http_allowed()
        self.check_ratelimit()
        logger.info("POST %s", args)
        response = self.session.post(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code == 429:
            _raise_discord_rate_limit(response)
        if response.status_code == 400:
            logger.error(response.json())
        response.raise_for_status()
        return response

    @on_exception(expo, RateLimitException, **_DISCORD_RATE_LIMIT_RETRY)
    def put(self, *args, **kwargs):
        """Put a resource using REST API"""
        _assert_discord_http_allowed()
        self.check_ratelimit()
        logger.info("PUT %s", args)
        response = self.session.put(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code == 429:
            _raise_discord_rate_limit(response)
        response.raise_for_status()
        return response

    @on_exception(expo, RateLimitException, **_DISCORD_RATE_LIMIT_RETRY)
    def patch(self, *args, **kwargs):
        """Patch a resource using REST API"""
        _assert_discord_http_allowed()
        self.check_ratelimit()
        logger.info("PATCH %s", args)
        response = self.session.patch(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code == 429:
            _raise_discord_rate_limit(response)
        response.raise_for_status()
        return response

    @on_exception(expo, RateLimitException, **_DISCORD_RATE_LIMIT_RETRY)
    def get(self, *args, **kwargs):
        """Get a resource using REST API"""
        _assert_discord_http_allowed()
        self.check_ratelimit()
        logger.info("GET %s", args)
        response = self.session.get(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code == 429:
            _raise_discord_rate_limit(response)
        response.raise_for_status()
        return response.json()

    @on_exception(expo, RateLimitException, **_DISCORD_RATE_LIMIT_RETRY)
    def delete(self, *args, **kwargs):
        """Delete a resource using REST API"""
        _assert_discord_http_allowed()
        self.check_ratelimit()
        response = self.session.delete(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code == 429:
            _raise_discord_rate_limit(response)
        if response.status_code == 404:
            # Don't throw exception for failing to delete if it doesn't exist
            return response
        response.raise_for_status()
        return response


DISCORD_OAUTH_SCOPES = "identify guilds.join"
DISCORD_OAUTH_SCOPES_URL = "identify%20guilds.join"


def discord_authorize_url(client_id: str, redirect_uri: str) -> str:
    """Discord OAuth authorize URL for site login (identify + guilds.join)."""
    return (
        "https://discord.com/api/oauth2/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code&scope={DISCORD_OAUTH_SCOPES_URL}"
    )


class DiscordClient(DiscordBaseClient):
    """Discord API Client"""

    def exchange_code(self, code: str, redirect_uri: str):
        """Exchange OAuth code for ``(user_profile, access_token)``."""
        _assert_discord_http_allowed()
        data = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "scope": DISCORD_OAUTH_SCOPES,
        }
        logger.debug("Discord OAuth2 Token Body: %s", data)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(
            "https://discord.com/api/oauth2/token",
            data=data,
            headers=headers,
            timeout=10,
        )

        if response.status_code >= 400:
            raise DiscordError.for_response(
                "Error exchanging token", "EXCHG_CODE", response
            )
        logger.debug("Discord OAuth2 Token Response: %s", response.json())
        credentials = response.json()
        access_token = credentials["access_token"]
        response = requests.get(
            "https://discord.com/api/v6/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if response.status_code >= 400:
            raise DiscordError.for_response(
                "Error fetching Discord profile", "GET_PROFILE", response
            )

        user = response.json()
        return user, access_token

    def add_guild_member(self, user_id: int | str, access_token: str) -> None:
        """Add user to the guild via OAuth ``guilds.join`` (201/204 = success)."""
        try:
            self.put(
                f"{BASE_URL}/guilds/{self.guild_id}/members/{user_id}",
                json={"access_token": access_token},
            )
        except requests.exceptions.HTTPError as exc:
            response = exc.response
            if response is None:
                raise
            logger.error(
                "Add Guild Member failed for user %s guild %s: %s %s",
                user_id,
                self.guild_id,
                response.status_code,
                response.text,
            )
            raise DiscordError.for_response(
                "Error adding Discord guild member",
                "GUILD_JOIN",
                response,
            ) from exc

    def complete_oauth_login(self, code: str, redirect_uri: str) -> dict:
        """Exchange OAuth code and add the user to the guild; fail closed on join."""
        user, access_token = self.exchange_code(code, redirect_uri)
        self.add_guild_member(user["id"], access_token)
        return user

    def get_channel(self, channel_id):
        """Get a discord channel by id (includes forum available_tags)."""
        return self.get(f"{BASE_URL}/channels/{channel_id}")

    def create_forum_thread(
        self,
        channel_id,
        title,
        message,
        applied_tags=None,
        components=None,
    ):
        """Create a forum thread in a discord channel.

        applied_tags: optional list of forum tag snowflake ids. Required by
        Discord when the forum channel has the REQUIRE_TAG flag enabled.
        components: optional Discord message component rows (buttons).
        """
        payload = {
            "name": title,
            "message": {
                "content": message,
            },
        }
        if components:
            payload["message"]["components"] = components
        if applied_tags:
            payload["applied_tags"] = [str(tag_id) for tag_id in applied_tags]
        return self.post(
            f"{BASE_URL}/channels/{channel_id}/threads",
            json=payload,
        )

    def get_message(self, channel_id, message_id):
        """Get a message from a discord channel"""
        return self.get(
            f"{BASE_URL}/channels/{channel_id}/messages/{message_id}",
        )

    def get_messages(self, channel_id, limit=100):
        """Get messages from a discord channel"""
        return self.get(
            f"{BASE_URL}/channels/{channel_id}/messages?limit={limit}",
        )

    def create_message(self, channel_id, message=None, payload=None):
        """Create a message in a discord channel
        Must have payload or message specified
        """
        if not message and not payload:
            raise ValueError("Must have message or payload specified")
        if not payload:
            payload = {"content": message}
        return self.post(
            f"{BASE_URL}/channels/{channel_id}/messages",
            json=payload,
        )

    def create_dm_channel(self, discord_user_id: str) -> dict:
        """Open (or retrieve) a DM channel with a Discord user."""
        return self.post(
            f"{BASE_URL}/users/@me/channels",
            json={"recipient_id": discord_user_id},
        ).json()

    def send_dm(
        self, discord_user_id: str, message: str = None, payload: dict = None
    ) -> dict:
        """Send a direct message to a Discord user by their Discord snowflake ID."""
        channel = self.create_dm_channel(discord_user_id)
        return self.create_message(
            channel["id"], message=message, payload=payload
        )

    def update_message(
        self, channel_id, message_id, message=None, payload=None
    ):
        """Update a message in a discord channel
        Must have payload or message specified
        """
        if not message and not payload:
            raise ValueError("Must have message or payload specified")
        if not payload:
            payload = {"content": message}
        return self.patch(
            f"{BASE_URL}/channels/{channel_id}/messages/{message_id}",
            json=payload,
        )

    def delete_message(self, channel_id, message_id):
        """Delete a message from a discord channel"""
        return self.delete(
            f"{BASE_URL}/channels/{channel_id}/messages/{message_id}",
        )

    def rename_thread(self, channel_id, name: str):
        """Rename a discord thread (max 100 characters)."""
        return self.patch(
            f"{BASE_URL}/channels/{channel_id}",
            json={
                "name": (name or "")[:100],
            },
        )

    def close_thread(self, channel_id):
        """Close a discord thread"""
        return self.patch(
            f"{BASE_URL}/channels/{channel_id}",
            json={
                "archived": True,
                "locked": True,
            },
        )

    def get_roles(self):
        """Get all roles from a discord server"""
        return self.get(
            f"{BASE_URL}/guilds/{self.guild_id}/roles",
        )

    def get_emojis(self):
        """Get all emojis from a discord server"""
        return self.get(
            f"{BASE_URL}/guilds/{self.guild_id}/emojis",
        )

    def get_members(self):
        """Get all members from a discord server"""
        member_count = self.get(
            f"{BASE_URL}/guilds/{self.guild_id}?with_counts=true",
        )["approximate_member_count"]

        # query in limits of 1000 based on member count
        members = []
        highest_member_id = 0
        for _ in range(0, member_count, 1000):
            response = self.get(
                f"{BASE_URL}/guilds/{self.guild_id}/members?limit=1000&after={highest_member_id}",
            )
            # sort by members[0]['user']['id']
            response = sorted(response, key=lambda x: int(x["user"]["id"]))
            highest_member_id = int(response[-1]["user"]["id"])
            members.extend(response)

        return members

    def create_role(self, name):
        """Create a role on a discord server"""
        return self.post(
            f"{BASE_URL}/guilds/{self.guild_id}/roles",
            json={
                "name": name,
            },
        )

    def edit_role(self, role_id, name):
        """Edit a role on a discord server"""
        return self.patch(
            f"{BASE_URL}/guilds/{self.guild_id}/roles/{role_id}",
            json={
                "name": name,
            },
        )

    def delete_role(self, role_id):
        """Delete a role from a discord server"""
        return self.delete(
            f"{BASE_URL}/guilds/{self.guild_id}/roles/{role_id}",
        )

    def get_user(self, user_id):
        """Get a user from a discord server"""
        return self.get(
            f"{BASE_URL}/guilds/{self.guild_id}/members/{user_id}",
        )

    def update_user(self, user_id, nickname: str):
        """Update a user on a discord server. Nickname is truncated to Discord's 32-char limit."""
        nick = (nickname or "")[:DISCORD_NICKNAME_MAX_LENGTH]
        data = {
            "nick": nick,
        }
        return self.patch(
            f"{BASE_URL}/guilds/{self.guild_id}/members/{user_id}",
            json=data,
        )

    def add_user_role(self, user_id, role_id):
        """Add a role to a user"""
        return self.put(
            f"{BASE_URL}/guilds/{self.guild_id}/members/{user_id}/roles/{role_id}",
        )

    def remove_user_role(self, user_id, role_id):
        """Remove a role from a user"""
        return self.delete(
            f"{BASE_URL}/guilds/{self.guild_id}/members/{user_id}/roles/{role_id}",
        )

    def create_guild_webhook(self, channel_id: int, name: str):
        """Create a guild webhook"""
        return self.post(
            f"{BASE_URL}/channels/{channel_id}/webhooks",
            json={
                "name": name,
            },
        ).json()

    def get_guild_channels(self, guild_id=None):
        """Get all channels from a guild."""
        type_map = {
            0: "text",
            2: "voice",
            4: "category",
            13: "stage",
            15: "forum",
        }
        target_guild_id = guild_id or self.guild_id
        channels = self.get(f"{BASE_URL}/guilds/{target_guild_id}/channels")
        return [
            {
                "id": int(channel["id"]),
                "name": channel["name"],
                "type": type_map.get(channel["type"], "unknown"),
                "guild_id": int(target_guild_id),
            }
            for channel in channels
        ]

    def get_bot_guilds(self):
        """Get all guilds the bot user is a member of."""
        guilds = self.get(f"{BASE_URL}/users/@me/guilds")
        return [
            {
                "id": int(guild["id"]),
                "name": guild["name"],
            }
            for guild in guilds
        ]
