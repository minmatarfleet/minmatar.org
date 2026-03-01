from django.db import models


class TribeGroupRequirementAssetType(models.Model):
    """
    An EVE type that satisfies a TribeGroupRequirement with type 'asset_type'.
    Owning >= requirement.minimum_count of ANY row in this table qualifies the character.
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
        help_text="EVE ship/item type that qualifies the character.",
    )
    minimum_count = models.PositiveIntegerField(
        default=1,
        help_text="Minimum number of this asset the character must own.",
    )
    location_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Required asset location (station/structure ID). Leave blank for any location.",
    )

    class Meta:
        ordering = ["eve_type__name"]
        verbose_name = "Asset Type"
        verbose_name_plural = "Asset Types"

    def __str__(self):
        return self.eve_type.name
