"""Database models for Discord integration"""

import logging

from django.contrib.auth.models import Group, User
from django.db import models

from discord.client import DiscordClient

# Create your models here.
discord = DiscordClient()
logger = logging.getLogger(__name__)


class DiscordUser(models.Model):
    """Representation of an external Discord user"""

    id = models.BigIntegerField(primary_key=True)
    discord_tag = models.CharField(max_length=100)
    avatar = models.CharField(max_length=100, blank=True, null=True)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="discord_user"
    )
    nickname = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return str(self.discord_tag)


class DiscordRole(models.Model):
    """Representation of an external Discord role on a Discord server"""

    role_id = models.BigIntegerField(blank=True, unique=True)
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(DiscordUser, related_name="groups")
    group = models.OneToOneField(
        Group, on_delete=models.CASCADE, related_name="discord_group"
    )

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        indexes = [
            models.Index(fields=["role_id"]),
        ]
