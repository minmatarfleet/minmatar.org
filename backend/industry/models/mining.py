from django.conf import settings
from django.db import models


class MiningUpgradeCompletion(models.Model):
    """Record of a mining anomaly completion in a system (timer derived from sovereignty mining level)."""

    system_id = models.BigIntegerField(db_index=True)
    system_name = models.CharField(max_length=255, blank=True)
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
            models.Index(fields=["system_id", "-completed_at"]),
        ]

    def __str__(self):
        return f"System {self.system_id} @ {self.completed_at}"
