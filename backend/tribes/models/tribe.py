from django.db import models


class Tribe(models.Model):
    """Top-level organisational container. Players join TribeGroups, not Tribes directly."""

    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    content = models.TextField(
        blank=True, help_text="Markdown-formatted long-form description."
    )
    image_url = models.URLField(null=True, blank=True)
    banner_url = models.URLField(null=True, blank=True)
    group = models.OneToOneField(
        "auth.Group",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tribe",
        help_text="Tribe-level Discord role (e.g. 'Capitals').",
    )
    discord_channel_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Tribe-level Discord channel for announcements.",
    )
    # The tribe's own Discord, where the chief maps existing roles.
    # Distinct from discord_channel_id, which is a channel on the alliance Discord.
    discord_guild = models.ForeignKey(
        "discord.DiscordGuild",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tribes",
    )
    chief = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="led_tribes",
        help_text="Single tribe leader; can approve/deny membership across all groups.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
