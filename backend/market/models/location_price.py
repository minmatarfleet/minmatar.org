"""
Live sell / buy / split prices per (location, eve type).

“ItemPrice” in conversation usually means this model
(EveMarketItemLocationPrice): current order-book aggregates at one
EveLocation (prices_active), not the Jita regional guide.

For Jita/Forge guide prices use EveMarketItemHistory via
market.helpers.pricing.get_prices_by_type_id — see docs/market-pricing.md.
"""

from django.db import models
from django.utils import timezone

from eveuniverse.models import EveType
from eveonline.models import EveLocation


class EveMarketItemLocationPrice(models.Model):
    """
    One row per (location, item): lowest sell, highest station-range buy,
    and split from the live ESI order book at that location.

    Synced for EveLocation.prices_active (not market_active). Not the
    canonical Jita guide — use EveMarketItemHistory / get_prices_by_type_id.
    """

    location = models.ForeignKey(
        EveLocation,
        on_delete=models.CASCADE,
        related_name="market_item_prices",
    )
    item = models.ForeignKey(
        EveType,
        on_delete=models.CASCADE,
        related_name="market_location_prices",
    )
    sell_price = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        help_text="Lowest sell order price at this location.",
    )
    buy_price = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Highest buy order price at this location; null if no buy orders.",
    )
    split_price = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="(sell_price + buy_price) / 2; null when buy_price is null.",
    )
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "EVE market item location price"
        verbose_name_plural = "EVE market item location prices"
        constraints = [
            models.UniqueConstraint(
                fields=["location", "item"],
                name="market_itemlocprice_loc_item",
            ),
        ]
        ordering = ["location", "item"]

    def __str__(self):
        return f"{self.item.name} @ {self.location.location_name}"
