from django.db import models


class TribeGroup(models.Model):
    """
    The actual joinable unit within a tribe.
    A single-focus tribe (e.g. Mining) has one TribeGroup.
    A multi-focus tribe (e.g. Capitals) has several (Dreads, Carriers, Fax).
    """

    tribe = models.ForeignKey(
        "tribes.Tribe", on_delete=models.CASCADE, related_name="groups"
    )
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    group = models.OneToOneField(
        "auth.Group",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tribe_group",
        help_text="Group-level Discord role (e.g. 'Dreads').",
    )
    chief = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="led_tribe_groups",
        help_text="Group leader; can approve/deny membership for this group.",
    )
    elders = models.ManyToManyField(
        "auth.User",
        blank=True,
        related_name="elder_tribe_groups",
        help_text="Supporting leaders; can also approve/deny membership for this group.",
    )
    discord_channel_id = models.BigIntegerField(null=True, blank=True)
    ship_type_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="EVE type IDs (hull IDs) used to attribute kills/losses/fleet events to this group.",
    )
    blueprint_type_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="Blueprint type IDs used to attribute industry jobs to this group.",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.tribe.name} — {self.name}"

    class Meta:
        ordering = ["tribe__name", "name"]
        unique_together = [("tribe", "name")]
