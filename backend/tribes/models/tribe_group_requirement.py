from django.db import models


class TribeGroupRequirement(models.Model):
    """
    Eligibility gate for joining a TribeGroup.

    Within a single requirement, all conditions AND together:
    - If qualifying_skills are defined, the character must have ALL of them at their minimum_level.
    - If asset_types are defined, the character must own >= minimum_count of ANY listed type.
    - If both are defined, both conditions must be satisfied.

    Multiple TribeGroupRequirement objects on the same group are OR'd: a character
    satisfies the group's requirements if they meet ANY one of them.
    """

    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="requirements",
    )

    # --- asset_type condition ---
    # Qualifying types (with per-type minimum_count and location_id) are stored
    # in the related TribeGroupRequirementAssetType model.
    # Owning >= minimum_count of ANY listed type satisfies this condition (OR across types).

    # --- skill condition ---
    # Qualifying skills are stored in the related TribeGroupRequirementSkill model.
    # All listed skills must be trained to their minimum_level (AND across skills).

    def __str__(self):
        return f"Requirement #{self.pk} ({self.tribe_group})"

    class Meta:
        ordering = ["tribe_group"]
