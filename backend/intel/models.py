import secrets

from django.contrib.auth.models import User
from django.db import models


def new_public_id() -> str:
    return secrets.token_urlsafe(8)


class IntelReport(models.Model):
    """A d-scan or Local list a pilot shared to the alliance intel sheet."""

    class Kind(models.TextChoices):
        DSCAN = "dscan", "D-scan"
        LOCAL = "local", "Local"

    # Shared links use this, not the row id, so reports can't be walked.
    public_id = models.CharField(
        max_length=16, unique=True, default=new_public_id, editable=False
    )
    kind = models.CharField(max_length=8, choices=Kind.choices)
    solar_system_id = models.BigIntegerField(null=True, blank=True)
    system_name = models.CharField(max_length=64, blank=True, default="")
    reporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intel_reports",
    )
    reporter_name = models.CharField(max_length=64, blank=True, default="")
    note = models.CharField(max_length=200, blank=True, default="")
    raw = models.TextField()
    # The parsed breakdown (services.ships.summarize_dscan /
    # services.local.summarize_local), computed once when shared.
    summary = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["solar_system_id", "kind", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.system_name} {self.public_id}"
