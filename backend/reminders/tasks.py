import logging
import random

import requests
from django.conf import settings

from app.celery import app
from discord.client import DiscordClient
from reminders.industry_daily_summary import (
    build_industry_daily_summary_message,
)
from reminders.messages.rat_quotes import rat_quotes

logger = logging.getLogger(__name__)


@app.task
def get_rat_quote():
    webhook_urls = [
        settings.DISCORD_HOLY_RAT_WEBHOOK_MINMATAR_FLEET,
        settings.DISCORD_HOLY_RAT_WEBHOOK_RAT_CAVE,
    ]
    # message is in format "book - quote"
    message = random.choice(rat_quotes)
    message = message.split("-")
    message = f"> {message[1]}\n> {message[0]}"

    for webhook_url in webhook_urls:
        requests.post(
            webhook_url,
            json={"content": message},
            timeout=5,
        )


@app.task
def send_industry_daily_summary():
    """Post industry order overview to the industry Discord channel (daily beat)."""
    channel_id = getattr(settings, "DISCORD_INDUSTRY_CHANNEL_ID", None)
    if not channel_id:
        logger.info(
            "DISCORD_INDUSTRY_CHANNEL_ID unset or 0; skipping industry summary"
        )
        return
    message = build_industry_daily_summary_message()
    try:
        DiscordClient().create_message(channel_id, message)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Failed to post industry daily summary to Discord channel %s: %s",
            channel_id,
            exc,
        )
