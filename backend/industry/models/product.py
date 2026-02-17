from django.db import models


class IndustryProductStrategy(models.TextChoices):
    """How we source or use this type in our industry chain."""

    IMPORT = "import", "Import"
    EXPORT = "export", "Export"
    INTEGRATED = "integrated", "Integrated"


class IndustryProduct(models.Model):
    """
    An Eve type we track as an industry product, with a strategy for how we
    source or use it: import, export, or integrated (utilize in our production chain).

    breakdown: optional cached nested component tree (root quantity=1). Stored tree
    is the full traverse all the way down to leaves so callers can traverse at
    whatever depth they want. Use get_breakdown_for_industry_product() to fetch
    or compute (and store) it; scale quantities when serving.
    """

    eve_type = models.OneToOneField(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
        related_name="industry_product",
    )
    strategy = models.CharField(
        max_length=16,
        choices=IndustryProductStrategy.choices,
    )
    breakdown = models.JSONField(
        null=True,
        blank=True,
        help_text="Full-depth nested component tree (root quantity=1). From get_breakdown_for_industry_product.",
    )

    class Meta:
        verbose_name = "industry product"
        verbose_name_plural = "industry products"

    def __str__(self):
        return f"{self.eve_type.name} ({self.get_strategy_display()})"
