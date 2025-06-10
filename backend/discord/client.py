"""Client wrapper for interacting with Discord API"""

import logging

import requests
from backoff import expo, on_exception
from django.conf import settings
from ratelimit import RateLimitException, limits
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from app.errors import create_error_id

logger = logging.getLogger(__name__)

GUILD_ID = 1041384161505722368
BASE_URL = "https://discord.com/api/v9"


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


class DiscordBaseClient:
    """Base Discord API Client"""

    def __init__(self):
        self.access_token = settings.DISCORD_BOT_TOKEN
        self.guild_id = GUILD_ID
        self.session = s

    @limits(calls=5, period=1)
    def check_ratelimit(self):
        pass

    @on_exception(expo, RateLimitException, max_tries=8)
    def post(self, *args, **kwargs):
        """Post a resource using REST API"""
        self.check_ratelimit()
        logger.info("POST %s", args)
        response = self.session.post(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code == 429:
            raise RateLimitException
        if response.status_code == 400:
            logger.error(response.json())
        response.raise_for_status()
        return response

    @on_exception(expo, RateLimitException, max_tries=8)
    def put(self, *args, **kwargs):
        """Put a resource using REST API"""
        self.check_ratelimit()
        logger.info("PUT %s", args)
        response = self.session.put(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code == 429:
            raise RateLimitException
        response.raise_for_status()
        return response

    @on_exception(expo, RateLimitException, max_tries=8)
    def patch(self, *args, **kwargs):
        """Patch a resource using REST API"""
        self.check_ratelimit()
        logger.info("PATCH %s", args)
        response = self.session.patch(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code == 429:
            raise RateLimitException
        response.raise_for_status()
        return response

    @on_exception(expo, RateLimitException, max_tries=8)
    def get(self, *args, **kwargs):
        """Get a resource using REST API"""
        self.check_ratelimit()
        logger.info("GET %s", args)
        response = self.session.get(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code == 429:
            raise RateLimitException
        response.raise_for_status()
        return response.json()

    @on_exception(expo, RateLimitException, max_tries=8)
    def delete(self, *args, **kwargs):
        """Delete a resource using REST API"""
        self.check_ratelimit()
        response = self.session.delete(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code == 429:
            raise RateLimitException
        if response.status_code == 404:
            # Don't throw exception for failing to delete if it doesn't exist
            return response
        response.raise_for_status()
        return response


class DiscordClient(DiscordBaseClient):
    """Discord API Client"""

    def exchange_code(self, code: str, redirect_uri: str):
        """Exchange a Discord OAuth2 code for an access token"""
        data = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "scope": "identify",
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
        # response.raise_for_status()
        credentials = response.json()
        access_token = credentials["access_token"]
        response = requests.get(
            "https://discord.com/api/v6/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        # response.raise_for_status()
        if response.status_code >= 400:
            raise DiscordError.for_response(
                "Error fetching Discord profile", "GET_PROFILE", response
            )

        user = response.json()
        return user

    def create_forum_thread(self, channel_id, title, message):
        """Create a forum thread in a discord channel"""
        return self.post(
            f"{BASE_URL}/channels/{channel_id}/threads",
            json={
                "name": title,
                "message": {
                    "content": message,
                },
            },
        )

    def get_message(self, channel_id, message_id):
        """Get a message from a discord channel"""
        return self.get(
            f"{BASE_URL}/channels/{channel_id}/messages/{message_id}",
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
        """Update a user on a discord server"""
        data = {
            "nick": nickname,
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
