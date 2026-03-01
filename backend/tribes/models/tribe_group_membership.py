from django.db import models


class TribeGroupMembership(models.Model):
    """
    Full lifecycle of a player's membership in a TribeGroup.
    Covers application → approval/denial → departure. Re-joining creates a new row.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DENIED = "denied"
    STATUS_LEFT = "left"
    STATUS_REMOVED = "removed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DENIED, "Denied"),
        (STATUS_LEFT, "Left"),
        (STATUS_REMOVED, "Removed"),
    ]

    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="tribe_memberships"
    )
    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    requirement_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Per-character compliance dict computed at submission time, stored for reviewer.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_tribe_memberships",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when status becomes 'left' or 'removed'.",
    )
    removed_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="removed_tribe_memberships",
    )

    def __str__(self):
        return f"{self.user} in {self.tribe_group} ({self.status})"

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tribe_group", "user"],
                condition=models.Q(status="approved"),
                name="tribes_tribegroupmembership_one_active_per_user_group",
            )
        ]


class TribeGroupMembershipCharacter(models.Model):
    """
    Tracks which specific EveCharacter instances a player has committed to a TribeGroup membership.
    Evaluated for requirements; activities are attributed per committed character.
    """

    LEAVE_REASON_VOLUNTARY = "voluntary"
    LEAVE_REASON_REMOVED = "removed"
    LEAVE_REASON_CHOICES = [
        (LEAVE_REASON_VOLUNTARY, "Voluntary"),
        (LEAVE_REASON_REMOVED, "Removed"),
    ]

    membership = models.ForeignKey(
        "tribes.TribeGroupMembership",
        on_delete=models.CASCADE,
        related_name="characters",
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="tribe_commitments",
    )
    committed_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    leave_reason = models.CharField(
        max_length=16, choices=LEAVE_REASON_CHOICES, null=True, blank=True
    )

    def __str__(self):
        return f"{self.character} → {self.membership.tribe_group}"

    class Meta:
        ordering = ["-committed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "character"],
                condition=models.Q(left_at__isnull=True),
                name="tribes_tribegroupmembershipchar_one_active_per_character",
            )
        ]
