from ratelimit import limits, RateLimitException
from backoff import on_exception, expo
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

GUILD_ID = 1041384161505722368


class DiscordBaseClient:
    """Base Discord API Client"""

    def __init__(self):
        self.access_token = settings.DISCORD_BOT_TOKEN
        self.guild_id = GUILD_ID

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=10, period=1)
    def post(self, *args, **kwargs):
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
        logger.info("GET %s", args)
        response = requests.get(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        if response.status_code != 204:
            logger.info(response.json())
        return response.json()

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=10, period=1)
    def delete(self, *args, **kwargs):
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

    def create_forum_thread(self, channel_id, title, message):
        return self.post(
            f"https://discord.com/api/v9/channels/{channel_id}/threads",
            json={
                "name": title,
                "message": {
                    "content": message,
                },
            },
        )

    def create_message(self, channel_id, message):
        return self.post(
            f"https://discord.com/api/v9/channels/{channel_id}/messages",
            json={
                "content": message,
            },
        )

    def close_thread(self, channel_id):
        return self.patch(
            f"https://discord.com/api/v9/channels/{channel_id}",
            json={
                "archived": True,
                "locked": True,
            },
        )

    def get_roles(self):
        return self.get(
            f"https://discord.com/api/v9/guilds/{self.guild_id}/roles",
        )

    def create_role(self, name):
        return self.post(
            f"https://discord.com/api/v9/guilds/{self.guild_id}/roles",
            json={
                "name": name,
            },
        )

    def edit_role(self, role_id, name):
        return self.patch(
            f"https://discord.com/api/v9/guilds/{self.guild_id}/roles/{role_id}",
            json={
                "name": name,
            },
        )

    def delete_role(self, role_id):
        return self.delete(
            f"https://discord.com/api/v9/guilds/{self.guild_id}/roles/{role_id}",
        )

    def add_user_role(self, user_id, role_id):
        return self.put(
            f"https://discord.com/api/v9/guilds/{self.guild_id}/members/{user_id}/roles/{role_id}",
        )

    def remove_user_role(self, user_id, role_id):
        return self.delete(
            f"https://discord.com/api/v9/guilds/{self.guild_id}/members/{user_id}/roles/{role_id}",
        )
