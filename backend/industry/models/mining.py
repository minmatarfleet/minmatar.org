from django.conf import settings
from django.db import models

from sovereignty.anomalies import (
    RESPAWN_MINUTES_BY_LEVEL,
    get_respawn_minutes as anomaly_respawn,
)
from sovereignty.services import get_mining_level_for_system


class MiningUpgradeCompletion(models.Model):
    """Record of a mining anomaly completion in a system (timer from site respawn or sovereignty mining level)."""

    sov_system = models.ForeignKey(
        "sovereignty.SystemSovereigntyConfig",
        on_delete=models.CASCADE,
        related_name="mining_completions",
    )
    site_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Anomaly/site name (e.g. Large Veldspar Deposit) for respawn lookup.",
    )
    completed_at = models.DateTimeField()
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mining_upgrade_completions",
    )

    class Meta:
        ordering = ["-completed_at"]
        verbose_name = "Mining upgrade completion"
        verbose_name_plural = "Mining upgrade completions"
        indexes = [
            models.Index(fields=["sov_system", "-completed_at"]),
        ]

    def __str__(self):
        name = self.sov_system.system_name or str(self.sov_system.system_id)
        return f"{name} @ {self.completed_at}" + (
            f" — {self.site_name}" if self.site_name else ""
        )

    def get_respawn_minutes(self) -> int | None:
        """
        Respawn time in minutes for this completion (from site name, else mining level fallback).
        """
        if self.site_name:
            minutes = anomaly_respawn(self.site_name)
            if minutes is not None:
                return minutes
        if self.sov_system_id:
            level = get_mining_level_for_system(self.sov_system.system_id)
            if level is not None:
                return RESPAWN_MINUTES_BY_LEVEL.get(level)
        return None
