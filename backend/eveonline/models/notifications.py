"""Every character notification ESI gives us, stored as received.

One poller reads ``/characters/{id}/notifications/`` for every character
with the notifications scope and keeps every row. Features read this table
instead of calling ESI themselves: structure pings and FW payouts are
transforms of it. ESI only returns recent notifications, so anything we did
not store is gone.
"""

from __future__ import annotations

from django.db import models


class EveCharacterNotification(models.Model):
    """One ESI notification for one character."""

    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_id = models.BigIntegerField()
    type = models.CharField(max_length=128, db_index=True)
    sender_id = models.BigIntegerField(null=True, blank=True)
    sender_type = models.CharField(max_length=32, blank=True, default="")
    timestamp = models.DateTimeField(db_index=True)
    is_read = models.BooleanField(null=True, blank=True)
    text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            models.UniqueConstraint(
                fields=["character", "notification_id"],
                name="unique_character_notification",
            )
        ]
        indexes = [
            models.Index(fields=["type", "-timestamp"]),
            models.Index(fields=["character", "-timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.character_id} {self.type} {self.notification_id}"

    def as_esi(self) -> dict:
        """The row in the shape ESI returned it, for parsers written for ESI."""
        return {
            "notification_id": self.notification_id,
            "type": self.type,
            "sender_id": self.sender_id,
            "sender_type": self.sender_type,
            "timestamp": self.timestamp,
            "is_read": self.is_read,
            "text": self.text,
        }
