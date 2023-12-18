from django.db import models
from django.contrib.auth.models import User, Group
from discord.client import DiscordClient
import logging

# Create your models here.
discord = DiscordClient()
logger = logging.getLogger(__name__)


class DiscordUser(models.Model):
    id = models.BigIntegerField(primary_key=True)
    discord_tag = models.CharField(max_length=100)
    avatar = models.CharField(max_length=100)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="discord_user"
    )

    def __str__(self):
        return str(self.discord_tag)


class DiscordRole(models.Model):
    role_id = models.BigIntegerField(blank=True)
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(DiscordUser, related_name="groups")
    group = models.OneToOneField(
        Group, on_delete=models.CASCADE, related_name="discord_group"
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        logger.info("Saving DiscordRole with role_id %s", self.role_id)
        if not self.role_id:
            logger.info(
                "No role_id, creating role based on group name %s",
                self.group.name,
            )
            role = discord.create_role(self.group.name)
            logger.info("Role created: %s", role.json())
            self.role_id = role.json()["id"]

        if self.group and not self.name:
            logger.info(
                "No name, setting name to group name %s", self.group.name
            )
            self.name = self.group.name

        if not self.group:
            logger.info(
                "No group, creating group based on role name %s", self.name
            )
            self.group = Group.objects.create(name=self.name)
        super().save(*args, **kwargs)
