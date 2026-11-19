"""Per-section freshness for character syncs (eveonline.character_sync)."""

from django.db import models


class EveCharacterSyncState(models.Model):
    """When one section of a character's ESI data was last synced, and when
    it is due again.

    The scheduler (``eveonline.tasks.character_sync``) only compares
    ``next_due_at`` with now; the interval is worked out when the row is
    stamped, so the per-tick query stays one indexed range scan.
    """

    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="sync_states",
    )
    section = models.CharField(max_length=32)
    next_due_at = models.DateTimeField()
    queued_at = models.DateTimeField(null=True, blank=True)
    attempted_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    consecutive_failures = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["character", "section"],
                name="eveonline_charsync_character_section",
            )
        ]
        indexes = [
            models.Index(
                fields=["section", "next_due_at"],
                name="eveonline_charsync_due",
            )
        ]

    def __str__(self):
        return f"{self.character_id}:{self.section} due {self.next_due_at}"
