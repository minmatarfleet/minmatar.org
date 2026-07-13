from __future__ import annotations

from django.db import models
from django.utils import timezone


class FeedMonitoredSystem(models.Model):
    class Source(models.TextChoices):
        FW_WARZONE = "fw_warzone", "FW warzone (seeded)"
        MANUAL = "manual", "Manual admin addition"

    solar_system_id = models.BigIntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=128)
    source = models.CharField(
        max_length=16, choices=Source.choices, default=Source.FW_WARZONE
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.solar_system_id})"


class FeedSystemContestedSnapshot(models.Model):
    """Hourly contested % reading for a monitored FW system."""

    solar_system_id = models.BigIntegerField(db_index=True)
    contested_percent = models.FloatField()
    occupier_faction_id = models.IntegerField(null=True, blank=True)
    victor_faction_id = models.IntegerField(null=True, blank=True)
    captured_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["solar_system_id", "-captured_at"]),
        ]
        ordering = ["-captured_at"]

    def __str__(self) -> str:
        return (
            f"System {self.solar_system_id} @ {self.contested_percent:.1f}% "
            f"({self.captured_at.isoformat()})"
        )


class FeedR2z2Cursor(models.Model):
    """Singleton cursor for R2Z2 poller."""

    last_sequence_id = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "R2Z2 cursor"

    @classmethod
    def get_singleton(cls) -> FeedR2z2Cursor:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class FeedKillmail(models.Model):
    killmail_id = models.BigIntegerField(unique=True, db_index=True)
    hash = models.CharField(max_length=64)
    killmail_time = models.DateTimeField(db_index=True)
    solar_system_id = models.BigIntegerField(db_index=True)
    victim_character_id = models.BigIntegerField(null=True, blank=True)
    victim_ship_type_id = models.BigIntegerField(null=True, blank=True)
    attacker_summary = models.JSONField(default=list)
    raw_killmail = models.JSONField()
    zkb_meta = models.JSONField(default=dict)
    zkill_sequence_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["solar_system_id", "killmail_time"]),
        ]
        ordering = ["-killmail_time"]

    def __str__(self) -> str:
        return f"Killmail {self.killmail_id}"


class FeedCharacterAffiliation(models.Model):
    """Cached militia enlistment for characters seen in the feed."""

    character_id = models.BigIntegerField(unique=True, db_index=True)
    faction_id = models.IntegerField(null=True, blank=True, db_index=True)
    corporation_id = models.BigIntegerField(null=True, blank=True)
    alliance_id = models.BigIntegerField(null=True, blank=True)
    esi_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When ESI affiliations last confirmed this row.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["esi_checked_at"]),
        ]
        ordering = ["character_id"]

    @property
    def esi_checked(self) -> bool:
        return self.esi_checked_at is not None

    def __str__(self) -> str:
        return f"Char {self.character_id} -> {self.faction_id}"


class FeedCluster(models.Model):
    class ClusterType(models.TextChoices):
        KILL_BURST = "kill_burst", "Kill burst"
        FLEET_ENGAGEMENT = "fleet_engagement", "Fleet engagement"

    cluster_type = models.CharField(max_length=32, choices=ClusterType.choices)
    cluster_key = models.CharField(max_length=256, unique=True)
    solar_system_id = models.BigIntegerField(db_index=True)
    dominant_faction_id = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField()
    last_kill_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    kill_count = models.PositiveIntegerField(default=0)
    pilot_count = models.PositiveIntegerField(default=0)
    ship_counts = models.JSONField(default=dict)
    attacker_ids = models.JSONField(default=list)
    killmail_ids = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["cluster_type", "is_active"]),
            models.Index(fields=["solar_system_id", "started_at"]),
        ]
        ordering = ["-last_kill_at"]

    def __str__(self) -> str:
        return self.cluster_key


class FeedRollupConfig(models.Model):
    rollup_code = models.CharField(max_length=64, unique=True)
    is_enabled = models.BooleanField(default=True)
    config = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Feed rollup config"

    def __str__(self) -> str:
        return self.rollup_code


class FeedEvent(models.Model):
    class Kind(models.TextChoices):
        FLEET_ACTIVE = "fleet_active", "Fleet active"
        KILLMAIL_BATCH = "killmail_batch", "Killmail batch"
        CONTESTED_CHANGE = "contested_change", "Contested change"

    class Accent(models.TextChoices):
        COMBAT = "combat", "Combat"
        MILITIA = "militia", "Militia"
        AMARR = "amarr", "Amarr"

    kind = models.CharField(max_length=32, choices=Kind.choices)
    occurred_at = models.DateTimeField(db_index=True)
    title = models.CharField(max_length=256)
    subheader = models.CharField(max_length=512, blank=True, default="")
    preview = models.TextField(blank=True, default="")
    body = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict)
    accent = models.CharField(
        max_length=16, choices=Accent.choices, default=Accent.COMBAT
    )
    rollup_code = models.CharField(max_length=64, db_index=True)
    rollup_version = models.PositiveIntegerField(default=1)
    cluster_key = models.CharField(
        max_length=256, blank=True, default="", db_index=True
    )
    source_type = models.CharField(max_length=64, blank=True, default="")
    source_id = models.BigIntegerField(null=True, blank=True)
    computed_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["-occurred_at", "-id"]),
            models.Index(fields=["rollup_code", "cluster_key"]),
            models.Index(fields=["source_type", "source_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["rollup_code", "cluster_key"],
                condition=models.Q(cluster_key__gt=""),
                name="feed_event_rollup_cluster_unique",
            ),
            models.UniqueConstraint(
                fields=["source_type", "source_id"],
                condition=models.Q(source_type__gt=""),
                name="feed_event_source_unique",
            ),
        ]
        ordering = ["-occurred_at", "-id"]

    def __str__(self) -> str:
        return f"{self.kind}: {self.title}"


class FeedEventKillmailLink(models.Model):
    feed_event = models.ForeignKey(
        FeedEvent, on_delete=models.CASCADE, related_name="killmail_links"
    )
    feed_killmail = models.ForeignKey(
        FeedKillmail, on_delete=models.CASCADE, related_name="event_links"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["feed_event", "feed_killmail"],
                name="feed_event_killmail_unique",
            ),
        ]


class FeedEventFleetLink(models.Model):
    feed_event = models.ForeignKey(
        FeedEvent, on_delete=models.CASCADE, related_name="fleet_links"
    )
    fleet_instance_id = models.BigIntegerField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["feed_event", "fleet_instance_id"],
                name="feed_event_fleet_unique",
            ),
        ]


class FeedCapitalPing(models.Model):
    """Discord capital-kill pings sent from the R2Z2 poller."""

    killmail_id = models.BigIntegerField(unique=True, db_index=True)
    solar_system_id = models.BigIntegerField()
    distance_ly = models.FloatField()
    discord_message_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Capital ping {self.killmail_id}"
