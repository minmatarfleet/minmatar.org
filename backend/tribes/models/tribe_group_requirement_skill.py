from django.db import models


class TribeGroupRequirementSkill(models.Model):
    """
    A qualifying skill for a TribeGroupRequirement with type 'skill'.
    The character satisfies the requirement if they have ANY listed skill
    trained to at least its minimum_level (OR logic).
    """

    requirement = models.ForeignKey(
        "tribes.TribeGroupRequirement",
        on_delete=models.CASCADE,
        related_name="qualifying_skills",
    )
    eve_type = models.ForeignKey(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        limit_choices_to={"eve_group__eve_category_id": 16},
        help_text="EVE skill type.",
    )
    minimum_level = models.PositiveIntegerField(
        default=5,
        help_text="Minimum trained level required (1–5).",
    )

    class Meta:
        ordering = ["eve_type__name"]
        verbose_name = "Qualifying Skill"
        verbose_name_plural = "Qualifying Skills"

    def __str__(self):
        return f"{self.eve_type.name} {self.minimum_level}"
