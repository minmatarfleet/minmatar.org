from django.db import models
from django.utils import timezone


class TribeGroupMembershipHistory(models.Model):
    """
    Append-only log of every TribeGroupMembership status transition.
    Written whenever the membership status changes (pending→active, active→inactive, etc.).
    """

    membership = models.ForeignKey(
        "tribes.TribeGroupMembership",
        on_delete=models.CASCADE,
        related_name="history",
    )
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16)
    changed_at = models.DateTimeField(default=timezone.now)
    changed_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tribe_membership_changes",
    )
    reason = models.CharField(
        max_length=32,
        blank=True,
        help_text="Optional machine-readable reason (e.g. 'denied', 'left', 'removed', 'approved').",
    )

    def __str__(self):
        return (
            f"{self.membership} {self.from_status}→{self.to_status} "
            f"at {self.changed_at}"
        )

    class Meta:
        ordering = ["changed_at"]


class TribeGroupMembershipCharacterHistory(models.Model):
    """
    Append-only log of character add/remove events on a TribeGroupMembership.
    - action='added': character was committed (committed_at lives here as 'at').
    - action='removed': character left or was removed (left_at and leave_reason live here).
    """

    ACTION_ADDED = "added"
    ACTION_REMOVED = "removed"
    ACTION_CHOICES = [
        (ACTION_ADDED, "Added"),
        (ACTION_REMOVED, "Removed"),
    ]

    LEAVE_REASON_VOLUNTARY = "voluntary"
    LEAVE_REASON_REMOVED = "removed"
    LEAVE_REASON_CHOICES = [
        (LEAVE_REASON_VOLUNTARY, "Voluntary"),
        (LEAVE_REASON_REMOVED, "Removed"),
    ]

    membership = models.ForeignKey(
        "tribes.TribeGroupMembership",
        on_delete=models.CASCADE,
        related_name="character_history",
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="tribe_character_history",
    )
    action = models.CharField(max_length=8, choices=ACTION_CHOICES)
    at = models.DateTimeField(default=timezone.now)
    by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tribe_character_history_actions",
    )
    leave_reason = models.CharField(
        max_length=16,
        choices=LEAVE_REASON_CHOICES,
        blank=True,
        help_text="Only set when action='removed'.",
    )

    def __str__(self):
        return (
            f"{self.action} {self.character} on {self.membership} at {self.at}"
        )

    class Meta:
        ordering = ["at"]
