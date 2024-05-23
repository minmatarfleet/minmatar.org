from reminders.messages.rat_quotes import rat_quotes
from app.celery import app
import random
import requests


@app.task
def get_rat_quote():
    webhook_urls = [
        "https://discord.com/api/webhooks/1243179286878359673/pwxa3PQaoKZ53xgB0XHw0u4xYVo7IPFovm-iVXwns_54ziuSu-YnbWb91m62N74BXmtj",  # minmatar fleet
        "https://discord.com/api/webhooks/1243183020383408248/aCmrwvimxYBFVEuxp9q0Dcnw4WJmJefjjLdegG4PBS4coE0BmUmzVoIlY9VTAHjCh8b9",  # rat cave
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
