from django.db import models


class TribeChiefVolunteer(models.Model):
    """
    A pilot offering to lead a tribe, or a group in it, that has no chief.

    ``tribe_group`` empty means the tribe chief seat. The alliance executor
    decides: appointing makes the pilot chief and closes every other open
    offer for that seat. A pilot has at most one pending offer per seat.
    """

    STATUS_PENDING = "pending"
    STATUS_APPOINTED = "appointed"
    STATUS_DECLINED = "declined"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPOINTED, "Appointed"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_CLOSED, "Closed"),
    ]

    NOTE_MAX_LENGTH = 500

    tribe = models.ForeignKey(
        "tribes.Tribe",
        on_delete=models.CASCADE,
        related_name="chief_volunteers",
    )
    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="chief_volunteers",
        help_text="Empty for the tribe chief seat.",
    )
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="tribe_chief_volunteers",
    )
    note = models.CharField(max_length=NOTE_MAX_LENGTH, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_tribe_chief_volunteers",
    )

    def __str__(self):
        seat = self.tribe_group or self.tribe
        return f"{self.user} for {seat} ({self.status})"

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["tribe", "tribe_group", "status"],
                name="tribes_chiefvol_seat_status",
            ),
        ]
