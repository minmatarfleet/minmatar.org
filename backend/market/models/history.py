from django.db import models

from eveuniverse.models import EveType


class EveMarketItemHistory(models.Model):
    """
    Daily region market history for an item in a region.

    One row per (region_id, item, date). Populated from ESI
    GET markets/{region_id}/history/?type_id=. Query via location.region_id
    (price_baseline region = Jita/Forge guide). Used by
    market.helpers.pricing.get_prices_by_type_id — preferred over
    EveMarketItemLocationPrice for appraisals and “Jita” guide prices.
    """

    region_id = models.BigIntegerField(
        db_index=True,
        null=True,
        blank=True,
        help_text="ESI region ID; history is per region so we fetch each item once per date.",
    )
    item = models.ForeignKey(
        EveType, on_delete=models.CASCADE, related_name="market_item_histories"
    )
    date = models.DateField(
        help_text="Day this history row is for (ESI date, e.g. midday snapshot)."
    )
    average = models.DecimalField(
        max_digits=32, decimal_places=2, help_text="Average price for the day."
    )
    highest = models.DecimalField(
        max_digits=32, decimal_places=2, help_text="Highest price for the day."
    )
    lowest = models.DecimalField(
        max_digits=32, decimal_places=2, help_text="Lowest price for the day."
    )
    order_count = models.BigIntegerField(
        default=0, help_text="Total number of orders executed that day."
    )
    volume = models.BigIntegerField(
        default=0, help_text="Total volume traded that day."
    )

    class Meta:
        verbose_name = "EVE market item history"
        verbose_name_plural = "EVE market item histories"
        constraints = [
            models.UniqueConstraint(
                fields=["region_id", "item", "date"],
                name="market_itemhist_region_item_date",
            ),
        ]
        indexes = [
            models.Index(
                fields=["region_id", "date"],
                name="market_itemhist_region_date",
            ),
            models.Index(
                fields=["item", "date"],
                name="market_itemhist_item_date",
            ),
        ]
        ordering = ["-date", "region_id", "item"]

    def __str__(self):
        return str(f"{self.item.name} region={self.region_id} {self.date}")
