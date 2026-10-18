from django.core.exceptions import ValidationError
from django.db import models


class TribeEvent(models.Model):
    """
    A Discord scheduled event published by a tribe group.

    Discord is where people mark themselves interested; the bot creates and
    edits the guild event and reads the interested count back.
    """

    RECURRENCE_NONE = "none"
    RECURRENCE_WEEKLY = "weekly"
    RECURRENCE_MONTHLY = "monthly"
    RECURRENCE_CHOICES = [
        (RECURRENCE_NONE, "Does not repeat"),
        (RECURRENCE_WEEKLY, "Weekly"),
        (RECURRENCE_MONTHLY, "Monthly (same weekday)"),
    ]

    WHERE_VOICE = "voice"
    WHERE_PLACE = "place"
    WHERE_CHOICES = [
        (WHERE_VOICE, "Discord voice channel"),
        (WHERE_PLACE, "Somewhere else"),
    ]

    STATUS_SCHEDULED = "scheduled"
    STATUS_CANCELLED = "cancelled"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_COMPLETED, "Completed"),
    ]

    tribe_group = models.ForeignKey(
        "tribes.TribeGroup", on_delete=models.CASCADE, related_name="events"
    )
    created_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tribe_events",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    recurrence = models.CharField(
        max_length=16, choices=RECURRENCE_CHOICES, default=RECURRENCE_NONE
    )
    where_kind = models.CharField(
        max_length=16, choices=WHERE_CHOICES, default=WHERE_VOICE
    )
    voice_channel_id = models.BigIntegerField(null=True, blank=True)
    voice_channel_name = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)
    members_only = models.BooleanField(default=False)
    announce = models.BooleanField(default=True)
    discord_event_id = models.BigIntegerField(null=True, blank=True)
    interested_count = models.IntegerField(default=0)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_SCHEDULED
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Discord shows a location event to the whole server.
        if self.members_only and self.where_kind != self.WHERE_VOICE:
            raise ValidationError(
                "A members-only event must be in a voice channel."
            )

    def __str__(self):
        return f"{self.tribe_group} — {self.title} ({self.starts_at:%Y-%m-%d})"

    class Meta:
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["status", "starts_at"])]
