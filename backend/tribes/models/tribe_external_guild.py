from django.db import models


class TribeExternalGuild(models.Model):
    """Secondary Discord guild for one tribe group (e.g. Pulse / Fishermen)."""

    tribe_group = models.OneToOneField(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="external_guild",
    )
    guild = models.ForeignKey(
        "discord.DiscordGuild",
        on_delete=models.PROTECT,
        related_name="tribe_group_bindings",
    )
    member_role_id = models.BigIntegerField(
        help_text="Discord role snowflake granted to active group members.",
    )
    alert_channel_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Channel for cleanup_failed alerts; falls back to chief DM.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tribe_group__name"]

    def __str__(self) -> str:
        return f"{self.tribe_group} → {self.guild.name}"


class TribeExternalGuildSeat(models.Model):
    """Durable Discord seat; survives User delete so kicks still work."""

    STATUS_PENDING_JOIN = "pending_join"
    STATUS_PRESENT = "present"
    STATUS_PENDING_REMOVE = "pending_remove"
    STATUS_REMOVED = "removed"
    STATUS_CLEANUP_FAILED = "cleanup_failed"
    STATUS_CHOICES = [
        (STATUS_PENDING_JOIN, "Pending join"),
        (STATUS_PRESENT, "Present"),
        (STATUS_PENDING_REMOVE, "Pending remove"),
        (STATUS_REMOVED, "Removed"),
        (STATUS_CLEANUP_FAILED, "Cleanup failed"),
    ]

    binding = models.ForeignKey(
        TribeExternalGuild,
        on_delete=models.CASCADE,
        related_name="seats",
    )
    user = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tribe_external_guild_seats",
    )
    discord_user_id = models.BigIntegerField()
    discord_username = models.CharField(max_length=100, blank=True, default="")
    discord_nickname = models.CharField(max_length=100, blank=True, default="")
    eve_name = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING_JOIN,
    )
    last_error = models.TextField(blank=True, default="")
    failure_count = models.PositiveIntegerField(default=0)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["binding", "discord_user_id"],
                name="tribes_external_guild_seat_unique_binding_discord",
            )
        ]

    def __str__(self) -> str:
        label = self.discord_username or str(self.discord_user_id)
        return f"{label} @ {self.binding} ({self.status})"
