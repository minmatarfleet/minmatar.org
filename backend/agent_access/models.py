"""Keys, limits and the audit log for AI agents (Claude) reaching Discord
and ESI.

The agent never holds the bot token. It calls the backend's MCP endpoint
(`agent_access/views.py`) with an `AgentKey`, and the backend makes the
Discord call itself, only through the tools in `agent_access/tools.py`.
ESI works the same way (`agent_access/esi_tools.py`): the agent never holds
a character's token, and reaches only the characters granted to its key.
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class AgentKey(models.Model):
    """A credential for one agent install (a cloud environment, one PC).

    Only a SHA-256 of the key is stored; the key is shown once, when it is
    created (`manage.py agent_key create` or the admin add form).
    """

    name = models.CharField(
        max_length=100,
        help_text='Where the key is used, e.g. "Claude cloud: Production".',
    )
    key_prefix = models.CharField(
        max_length=16,
        help_text="The start of the key, to recognise it. Not secret.",
    )
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    can_write = models.BooleanField(
        default=True,
        help_text=(
            "May use the write tools (send a message, react). Writes still "
            "need an allowed post target."
        ),
    )
    can_use_esi = models.BooleanField(
        default=False,
        help_text=(
            "May use the ESI endpoint, for the characters granted to this "
            "key under Agent ESI characters."
        ),
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Stops working after this time. Empty: never expires.",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.key_prefix}…)"

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > timezone.now()


class AgentDiscordSettings(models.Model):
    """Kill switches. A single row (pk=1); see `get()`."""

    enabled = models.BooleanField(
        default=True,
        help_text="Off: the agent endpoint answers 503 to every request.",
    )
    writes_enabled = models.BooleanField(
        default=True,
        help_text="Off: every write tool is refused; reads still work.",
    )
    writes_per_minute = models.PositiveIntegerField(
        default=6, help_text="Per key."
    )
    writes_per_day = models.PositiveIntegerField(
        default=100, help_text="Per key."
    )

    class Meta:
        verbose_name = "Agent Discord settings"
        verbose_name_plural = "Agent Discord settings"

    def __str__(self):
        return "Agent Discord settings"

    @classmethod
    def get(cls) -> "AgentDiscordSettings":
        row, _ = cls.objects.get_or_create(pk=1)
        return row


class AgentDiscordPostTarget(models.Model):
    """Where the agent may post. No row for a channel: writes are refused."""

    guild_id = models.CharField(max_length=32)
    channel_id = models.CharField(
        max_length=32,
        blank=True,
        help_text="Empty: any channel in the server.",
    )
    include_threads = models.BooleanField(
        default=True,
        help_text="Also allow threads whose parent is this channel.",
    )
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = [("guild_id", "channel_id")]

    def __str__(self):
        where = self.channel_id or "any channel"
        return f"{self.guild_id} / {where}"


class AgentDiscordReadBlock(models.Model):
    """A server or channel the agent may not read (or post in)."""

    guild_id = models.CharField(max_length=32)
    channel_id = models.CharField(
        max_length=32,
        blank=True,
        help_text=(
            "Empty: the whole server. A channel also blocks its threads."
        ),
    )
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = [("guild_id", "channel_id")]

    def __str__(self):
        where = self.channel_id or "whole server"
        return f"{self.guild_id} / {where}"


class AgentDiscordCall(models.Model):
    """One tool call, allowed or refused."""

    key = models.ForeignKey(
        AgentKey, on_delete=models.CASCADE, related_name="calls"
    )
    tool = models.CharField(max_length=64)
    is_write = models.BooleanField(default=False)
    guild_id = models.CharField(max_length=32, blank=True)
    channel_id = models.CharField(max_length=32, blank=True)
    arguments = models.JSONField(default=dict)
    ok = models.BooleanField(default=False)
    error = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["key", "is_write", "ok", "created_at"],
                name="agent_call_write_rate",
            ),
        ]

    def __str__(self):
        return (
            f"{self.tool} by {self.key_id} at {self.created_at:%Y-%m-%d %H:%M}"
        )


class AgentEsiSettings(models.Model):
    """Kill switch and limits for the ESI endpoint. A single row (pk=1)."""

    enabled = models.BooleanField(
        default=True,
        help_text="Off: the agent ESI endpoint refuses every request.",
    )
    calls_per_minute = models.PositiveIntegerField(
        default=30, help_text="Per key."
    )
    calls_per_day = models.PositiveIntegerField(
        default=1000, help_text="Per key."
    )
    blocked_paths = models.TextField(
        default="/mail",
        blank=True,
        help_text=(
            "One per line. A route containing any of these is refused, "
            'e.g. "/mail" blocks every character mail route.'
        ),
    )

    class Meta:
        verbose_name = "Agent ESI settings"
        verbose_name_plural = "Agent ESI settings"

    def __str__(self):
        return "Agent ESI settings"

    @classmethod
    def get(cls) -> "AgentEsiSettings":
        row, _ = cls.objects.get_or_create(pk=1)
        return row

    def blocked_fragments(self) -> list[str]:
        return [
            line.strip()
            for line in (self.blocked_paths or "").splitlines()
            if line.strip()
        ]


class AgentEsiCharacter(models.Model):
    """A character whose ESI token a key may use."""

    key = models.ForeignKey(
        AgentKey, on_delete=models.CASCADE, related_name="esi_characters"
    )
    character_id = models.BigIntegerField()
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text='Why, e.g. "Debugging asset sync for help ticket #123".',
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The grant stops working after this time. Empty: never.",
    )

    class Meta:
        verbose_name = "Agent ESI character"
        unique_together = [("key", "character_id")]

    def __str__(self):
        return f"{self.character_id} for {self.key}"

    @property
    def is_active(self) -> bool:
        return self.expires_at is None or self.expires_at > timezone.now()


class AgentEsiCall(models.Model):
    """One ESI tool call, allowed or refused."""

    key = models.ForeignKey(
        AgentKey, on_delete=models.CASCADE, related_name="esi_calls"
    )
    tool = models.CharField(max_length=64)
    character_id = models.BigIntegerField(null=True, blank=True)
    method = models.CharField(max_length=8, blank=True)
    path = models.CharField(max_length=300, blank=True)
    arguments = models.JSONField(default=dict)
    esi_status = models.PositiveIntegerField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    error = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["key", "created_at"], name="agent_esi_call_rate"
            ),
        ]

    def __str__(self):
        return (
            f"{self.tool} {self.path} by {self.key_id} "
            f"at {self.created_at:%Y-%m-%d %H:%M}"
        )
