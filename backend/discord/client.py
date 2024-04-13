"""Client wrapper for interacting with Discord API"""

import logging

import requests
from backoff import expo, on_exception
from django.conf import settings
from ratelimit import RateLimitException, limits

logger = logging.getLogger(__name__)

GUILD_ID = 1041384161505722368
BASE_URL = "https://discord.com/api/v9"


class DiscordBaseClient:
    """Base Discord API Client"""

    def __init__(self):
        self.access_token = settings.DISCORD_BOT_TOKEN
        self.guild_id = GUILD_ID

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=10, period=1)
    def post(self, *args, **kwargs):
        """Post a resource using REST API"""
        logger.info("POST %s", args)
        response = requests.post(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        logger.info(response.json())
        return response

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=10, period=1)
    def put(self, *args, **kwargs):
        """Put a resource using REST API"""
        logger.info("PUT %s", args)
        response = requests.put(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code != 204:
            logger.info(response.json())
        return response

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=10, period=1)
    def patch(self, *args, **kwargs):
        """Patch a resource using REST API"""
        logger.info("PATCH %s", args)
        response = requests.patch(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code != 204:
            logger.info(response.json())
        return response

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=10, period=1)
    def get(self, *args, **kwargs):
        """Get a resource using REST API"""
        logger.info("GET %s", args)
        response = requests.get(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        logger.info(response.json())
        logger.info(response.status_code)
        if response.status_code != 204:
            logger.info(response.json())
        return response.json()

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=10, period=1)
    def delete(self, *args, **kwargs):
        """Delete a resource using REST API"""
        response = requests.delete(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code != 204:
            logger.info(response.json())
        return response


class DiscordClient(DiscordBaseClient):
    """Discord API Client"""

    def exchange_code(self, code: str):
        """Exchange a Discord OAuth2 code for an access token"""
        data = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.DISCORD_REDIRECT_URL,
            "scope": "identify",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(
            "https://discord.com/api/oauth2/token",
            data=data,
            headers=headers,
            timeout=10,
        )
        credentials = response.json()
        print(credentials)
        access_token = credentials["access_token"]
        response = requests.get(
            "https://discord.com/api/v6/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
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

    def create_message(self, channel_id, message):
        """Create a message in a discord channel"""
        return self.post(
            f"{BASE_URL}/channels/{channel_id}/messages",
            json={
                "content": message,
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
