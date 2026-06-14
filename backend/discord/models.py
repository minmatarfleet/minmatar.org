"""Database models for Discord integration"""

import logging

import requests
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
    is_down_under = models.BooleanField(default=False)
    dress_wearer = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

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
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self) -> str:
        return str(self.name)

    def delete(self, *args, **kwargs):
        if self.role_id:
            try:
                discord.delete_role(self.role_id)
            except requests.HTTPError as e:
                logger.warning(
                    "Could not delete Discord role %s (id=%s): %s",
                    self.name,
                    self.role_id,
                    e,
                )
        super().delete(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["role_id"]),
        ]


class DiscordChannelActivityRecord(models.Model):
    TEXT_MESSAGE = "text_message"
    VOICE_MINUTE = "voice_minute"

    ACTIVITY_TYPE_CHOICES = [
        (TEXT_MESSAGE, "Text message"),
        (VOICE_MINUTE, "Voice minute"),
    ]

    created_on = models.DateTimeField(auto_now_add=True)
    activity_type = models.CharField(
        max_length=32, choices=ACTIVITY_TYPE_CHOICES
    )
    username = models.CharField(max_length=255)
    quantity = models.IntegerField(
        help_text="Minutes for voice activity, message count for text activity."
    )
    channel_id = models.BigIntegerField(null=True, blank=True)
    channel_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_on"], name="created_on_idx"),
            models.Index(fields=["username"], name="username_idx"),
            models.Index(
                fields=["channel_id", "created_on"],
                name="channel_created_on_idx",
            ),
            models.Index(
                fields=["activity_type", "created_on"],
                name="activity_type_created_on_idx",
            ),
        ]


class DiscordGuild(models.Model):
    guild_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=255)
    is_primary = models.BooleanField(
        default=False,
        help_text="Matches DISCORD_GUILD_ID in application settings.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Bot was present in this guild on the last sync.",
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DiscordChannel(models.Model):
    TEXT = "text"
    VOICE = "voice"
    STAGE = "stage"
    FORUM = "forum"
    CATEGORY = "category"
    UNKNOWN = "unknown"

    CHANNEL_TYPE_CHOICES = [
        (TEXT, "Text"),
        (VOICE, "Voice"),
        (STAGE, "Stage"),
        (FORUM, "Forum"),
        (CATEGORY, "Category"),
        (UNKNOWN, "Unknown"),
    ]

    channel_id = models.BigIntegerField(unique=True)
    guild = models.ForeignKey(
        DiscordGuild,
        on_delete=models.CASCADE,
        related_name="channels",
    )
    name = models.CharField(max_length=255)
    channel_type = models.CharField(
        max_length=32, choices=CHANNEL_TYPE_CHOICES
    )
    track_voice_activity = models.BooleanField(
        default=False,
        help_text=(
            "When enabled, the bot records voice presence in this channel each minute."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_channel_type_display()})"
