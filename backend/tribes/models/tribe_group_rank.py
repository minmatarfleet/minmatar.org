from django.db import models


class TribeGroupRank(models.Model):
    """
    Optional rank ladder within a TribeGroup (e.g. Strategic / Skirmish / Warzone FC).
    Memberships may reference at most one rank; groups with no ranks leave rank null.
    """

    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="ranks",
    )
    name = models.CharField(max_length=128)
    code = models.CharField(
        max_length=64,
        help_text="Stable key within the tribe group (e.g. strategic).",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Lower values sort first in UI lists.",
    )
    group = models.OneToOneField(
        "auth.Group",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tribe_group_rank",
        help_text="Auth group applied when a member holds this rank (e.g. Strategic FC).",
    )

    def __str__(self):
        return f"{self.tribe_group} — {self.name}"

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tribe_group", "code"],
                name="tribes_tribegrouprank_unique_code_per_group",
            )
        ]
