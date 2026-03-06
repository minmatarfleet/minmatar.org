from django.db import models


class TribeGroupRequirementAssetType(models.Model):
    """
    An EVE type that satisfies a TribeGroupRequirement with type 'asset_type'.
    Owning ANY row in this table qualifies the character.
    """

    requirement = models.ForeignKey(
        "tribes.TribeGroupRequirement",
        on_delete=models.CASCADE,
        related_name="asset_types",
    )
    eve_type = models.ForeignKey(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        limit_choices_to={"eve_group__eve_category_id": 6},
        help_text="EVE ship type that qualifies the character.",
    )
    locations = models.ManyToManyField(
        "eveonline.EveLocation",
        blank=True,
        limit_choices_to={"staging_active": True},
        help_text="Required asset locations (staging only). Leave blank for any location.",
    )

    class Meta:
        ordering = ["eve_type__name"]
        verbose_name = "Asset Type"
        verbose_name_plural = "Asset Types"

    def __str__(self):
        return self.eve_type.name
