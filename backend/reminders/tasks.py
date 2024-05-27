import random

import requests
from django.conf import settings

from app.celery import app
from reminders.messages.rat_quotes import rat_quotes


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
