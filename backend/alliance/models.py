from django.db import models
from django.utils import timezone


class AllianceHealthSnapshot(models.Model):
    """Cached alliance health rollup for staff dashboard reads."""

    computed_at = models.DateTimeField(default=timezone.now, db_index=True)
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ["-computed_at"]
        permissions = (
            ("view_alliancehealth", "Can view alliance health dashboard"),
        )

    def __str__(self) -> str:
        return f"AllianceHealthSnapshot {self.computed_at.isoformat()}"
