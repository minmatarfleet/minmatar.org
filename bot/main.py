from app.client import client
from app.settings import settings

client.run(settings.DISCORD_BOT_TOKEN)
