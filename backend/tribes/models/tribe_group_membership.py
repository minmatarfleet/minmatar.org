from django.db import models


class TribeGroupMembership(models.Model):
    """
    A player's membership in a TribeGroup.
    Exactly one row per (user, tribe_group) pair — enforced by a unique constraint.
    Status transitions (pending → active → inactive) are all tracked in
    TribeGroupMembershipHistory. Re-applying after going inactive resets
    this same row back to pending rather than creating a new one.
    """

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
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
        help_text="Set when status becomes inactive.",
    )
    removed_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="removed_tribe_memberships",
    )

    # ------------------------------------------------------------------
    # Transient attributes — set by callers before .save() to pass
    # context into the post_save signal without persisting extra data.
    # These are never stored in the database.
    # ------------------------------------------------------------------
    #: User who triggered the status change (written to history).
    history_changed_by = None
    #: Machine-readable reason when transitioning to inactive
    #: (e.g. "denied", "left", "removed").
    history_inactive_reason = ""
    #: Snapshot of status before save, populated by the pre_save signal.
    history_pre_save_status = None

    def __str__(self):
        return f"{self.user} in {self.tribe_group} ({self.status})"

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tribe_group", "user"],
                name="tribes_tribegroupmembership_unique_per_user_group",
            )
        ]


class TribeGroupMembershipCharacter(models.Model):
    """
    Current roster: records which EveCharacters are actively committed to a membership.
    This is the live state only — no audit fields here.
    All history (when added, when removed, why) lives in TribeGroupMembershipCharacterHistory.
    """

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

    def __str__(self):
        return f"{self.character} → {self.membership.tribe_group}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "character"],
                name="tribes_tribegroupmembershipchar_unique_per_membership",
            )
        ]
