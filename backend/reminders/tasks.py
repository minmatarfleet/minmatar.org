from reminders.messages.rat_quotes import rat_quotes
from app.celery import app
import random
import requests


@app.task
def get_rat_quote():
    webhook_url = "https://discord.com/api/webhooks/1243179286878359673/pwxa3PQaoKZ53xgB0XHw0u4xYVo7IPFovm-iVXwns_54ziuSu-YnbWb91m62N74BXmtj"
    # message is in format "book - quote"
    message = random.choice(rat_quotes)
    message = message.split("-")
    message = f"> {message[1]}\n> {message[0]}"

    requests.post(
        webhook_url,
        json={"content": message},
        timeout=5,
    )
