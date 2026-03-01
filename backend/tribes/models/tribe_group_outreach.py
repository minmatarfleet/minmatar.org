from django.db import models


class TribeGroupOutreach(models.Model):
    """
    Optional: tracks that a chief/elder reached out to a recruitment candidate.
    Prevents duplicate outreach and provides a recruitment history per group.
    """

    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="outreach_records",
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="tribe_outreach",
        help_text="The candidate character that was contacted.",
    )
    sent_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_tribe_outreach",
        help_text="Chief or elder who sent the outreach.",
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="E.g. 'DM'd on Discord'.")

    def __str__(self):
        return f"{self.sent_by} → {self.character} ({self.tribe_group})"

    class Meta:
        ordering = ["-sent_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tribe_group", "character"],
                name="tribes_tribegroupoutreach_unique_per_group_character",
            )
        ]
