from django.db import models


class TribeGroupRequirement(models.Model):
    """
    Eligibility gate for joining a TribeGroup. Requirements are stackable (AND logic).
    They gate applications and power the compliance snapshot — they do NOT auto-enroll anyone.
    """

    REQUIREMENT_TYPE_ASSET = "asset_type"
    REQUIREMENT_TYPE_SKILL = "skill"
    REQUIREMENT_TYPE_CHOICES = [
        (REQUIREMENT_TYPE_ASSET, "Asset Ownership"),
        (REQUIREMENT_TYPE_SKILL, "Qualifying Skill"),
    ]

    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="requirements",
    )
    requirement_type = models.CharField(
        max_length=32, choices=REQUIREMENT_TYPE_CHOICES
    )

    # --- asset_type requirement ---
    # Qualifying types (with per-type minimum_count and location_id) are stored
    # in the related TribeGroupRequirementAssetType model.
    # Owning >= minimum_count of ANY listed type satisfies this requirement (OR logic).

    # --- skill requirement ---
    # Qualifying skills are stored in the related TribeGroupRequirementSkill model.
    # All listed skills must be trained to their minimum_level (AND logic).

    def __str__(self):
        return f"{self.tribe_group} — {self.get_requirement_type_display()}"

    class Meta:
        ordering = ["tribe_group", "requirement_type"]
