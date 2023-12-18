from app.celery import app
from discord.client import DiscordClient
from django.contrib.auth.models import Group
import logging

discord = DiscordClient()
logging = logging.getLogger(__name__)


@app.task()
def poll_external_roles():
    roles = discord.get_roles()
    for role in roles:
        if not Group.objects.filter(name=role["name"]).exists():
            Group.objects.create(name=role["name"])
