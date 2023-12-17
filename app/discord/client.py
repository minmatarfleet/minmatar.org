import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class DiscordBaseClient:
    """Base Discord API Client"""

    def __init__(self):
        self.access_token = settings.DISCORD_BOT_TOKEN

    def post(self, *args, **kwargs):
        response = requests.post(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        logger.info(response.json())
        return response

    def patch(self, *args, **kwargs):
        response = requests.patch(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        logger.info(response.json())
        return response

    def get(self, *args, **kwargs):
        response = requests.get(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
        logger.info(response.json())
        return response

    def delete(self, *args, **kwargs):
        response = requests.delete(
            *args,
            **kwargs,
            headers={"Authorization": f"Bot {self.access_token}"},
            timeout=10,
        )
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
