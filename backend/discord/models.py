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

    def __str__(self):
        return str(self.discord_tag)


class DiscordRole(models.Model):
    """Representation of an external Discord role on a Discord server"""

    role_id = models.BigIntegerField(blank=True)
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(DiscordUser, related_name="groups")
    group = models.OneToOneField(
        Group, on_delete=models.CASCADE, related_name="discord_group"
    )

    def __str__(self) -> str:
        return str(self.name)

    def save(self, *args, **kwargs):
        logger.info("Saving DiscordRole with role_id %s", self.role_id)
        if not self.role_id:  # skip when importing a role
            # resolve existing role from discord server
            roles = discord.get_roles()
            existing_role = False
            for role in roles:
                if role["name"] == self.name:
                    logger.info("Found existing role with name %s", self.name)
                    self.role_id = role["id"]
                    existing_role = True
                    break

            # create role if no existing role on discord server
            if not existing_role:
                logger.info(
                    "No role_id, creating role based on group name %s",
                    self.group.name,
                )
                role = discord.create_role(self.group.name)
                logger.info("Role created: %s", role.json())
                self.role_id = role.json()["id"]

        super().save(*args, **kwargs)
