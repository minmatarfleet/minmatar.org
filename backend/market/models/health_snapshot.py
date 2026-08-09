from django.db import models

from eveonline.models import EveLocation


class EveMarketHealthSnapshot(models.Model):
    """
    Point-in-time market health for one kind at a market-active location.

    Writers run independently after contracts ESI sync or structure order sync.
    Built from local DB only.
    """

    KIND_CONTRACTS = "contracts"
    KIND_SELL_ORDERS = "sell_orders"
    KIND_CHOICES = (
        (KIND_CONTRACTS, "Contracts"),
        (KIND_SELL_ORDERS, "Sell orders"),
    )

    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    location = models.ForeignKey(
        EveLocation,
        on_delete=models.CASCADE,
        related_name="health_snapshots",
    )

    health_pct = models.FloatField(null=True, blank=True)
    viability_pct = models.FloatField(null=True, blank=True)
    targets = models.PositiveIntegerField(default=0)
    listed_targets = models.PositiveIntegerField(default=0)
    fulfilled = models.PositiveIntegerField(default=0)
    viable_fulfilled = models.PositiveIntegerField(default=0)
    isk = models.FloatField(default=0.0)
    synced_at = models.DateTimeField(null=True, blank=True)
    history_days = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "EVE market health snapshot"
        verbose_name_plural = "EVE market health snapshots"
        indexes = [
            models.Index(
                fields=["kind", "location", "-captured_at"],
                name="market_hlth_kind_loc_captured",
            ),
        ]
        ordering = ["-captured_at"]

    def __str__(self):
        return (
            f"{self.location.location_name} {self.kind} "
            f"@ {self.captured_at:%Y-%m-%d %H:%M}"
        )
