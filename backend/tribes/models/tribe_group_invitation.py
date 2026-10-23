from django.db import models


class TribeGroupInvitation(models.Model):
    """
    A chief asking a pilot into their group.

    Accepting skips review: the pilot's membership goes straight to active
    with the inviter as approver. A pilot has at most one pending invite
    per group; answered rows stay for the chief's Invitations list.
    """

    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_WITHDRAWN = "withdrawn"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_WITHDRAWN, "Withdrawn"),
        (STATUS_EXPIRED, "Expired"),
    ]

    NOTE_MAX_LENGTH = 300

    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="tribe_invitations",
        help_text="The invited pilot.",
    )
    invited_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_tribe_invitations",
    )
    note = models.CharField(max_length=NOTE_MAX_LENGTH, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    membership = models.ForeignKey(
        "tribes.TribeGroupMembership",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitations",
        help_text="The membership an accepted invite activated.",
    )

    def __str__(self):
        return f"{self.user} → {self.tribe_group} ({self.status})"

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["tribe_group", "user", "status"],
                name="tribes_invite_group_user_st",
            ),
            models.Index(
                fields=["status", "expires_at"],
                name="tribes_invite_status_expiry",
            ),
        ]
