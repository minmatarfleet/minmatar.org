from django.db import models
from django.utils import timezone

from eveuniverse.models import EveType
from eveonline.models import EveLocation


class EveMarketOrderBookSync(models.Model):
    """Per-location watermark for structure order-book snapshots."""

    location = models.OneToOneField(
        EveLocation,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="order_book_sync",
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "EVE market order book sync"
        verbose_name_plural = "EVE market order book syncs"

    def __str__(self):
        return (
            f"{self.location.location_name} "
            f"@ {self.last_synced_at or 'never'}"
        )


class EveMarketInferredSale(models.Model):
    """Append-only inferred sell fill from successive order-book snapshots."""

    REASON_PARTIAL_FILL = "partial_fill"
    REASON_SELLOUT = "sellout"
    REASON_CHOICES = [
        (REASON_PARTIAL_FILL, "Partial fill"),
        (REASON_SELLOUT, "Sellout"),
    ]

    location = models.ForeignKey(
        EveLocation,
        on_delete=models.CASCADE,
        related_name="inferred_sales",
    )
    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=32, decimal_places=2)
    inferred_at = models.DateTimeField(default=timezone.now, db_index=True)
    order_id = models.BigIntegerField(null=True, blank=True)
    reason = models.CharField(max_length=32, choices=REASON_CHOICES)

    class Meta:
        verbose_name = "EVE market inferred sale"
        verbose_name_plural = "EVE market inferred sales"
        indexes = [
            models.Index(
                fields=["location", "inferred_at"],
                name="market_infsale_loc_inferred",
            ),
            models.Index(
                fields=["location", "item", "inferred_at"],
                name="market_infsale_loc_item_inf",
            ),
        ]
        ordering = ["-inferred_at"]

    def __str__(self):
        return (
            f"{self.item_id} x{self.quantity} @ {self.price} "
            f"({self.reason}) {self.location_id}"
        )
