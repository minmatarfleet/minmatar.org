from django.db import models

from eveonline.models import EveLocation


class EveMarketOpsMonitorSnapshot(models.Model):
    """
    Point-in-time ops monitor health for a market-active location.

    Written after existing market ESI syncs finish (contracts / structure
    orders). Built from local DB state via build_ops_monitor — no extra ESI.
    """

    TRIGGER_CONTRACTS = "contracts"
    TRIGGER_ORDERS = "orders"
    TRIGGER_CHOICES = [
        (TRIGGER_CONTRACTS, "Contracts sync"),
        (TRIGGER_ORDERS, "Structure orders sync"),
    ]

    captured_at = models.DateTimeField(auto_now_add=True, db_index=True)
    location = models.ForeignKey(
        EveLocation,
        on_delete=models.CASCADE,
        related_name="ops_monitor_snapshots",
    )
    trigger = models.CharField(max_length=32, choices=TRIGGER_CHOICES)

    contracts_health_pct = models.FloatField(null=True, blank=True)
    sell_orders_health_pct = models.FloatField(null=True, blank=True)
    sell_orders_viability_pct = models.FloatField(null=True, blank=True)
    overall_health_pct = models.FloatField(null=True, blank=True)

    understocked_contracts_count = models.PositiveIntegerField(default=0)
    sell_gaps_count = models.PositiveIntegerField(default=0)
    contract_targets = models.PositiveIntegerField(default=0)
    contract_fulfilled = models.PositiveIntegerField(default=0)
    sell_order_targets = models.PositiveIntegerField(default=0)
    sell_order_fulfilled = models.PositiveIntegerField(default=0)
    sell_order_viable_fulfilled = models.PositiveIntegerField(default=0)

    contracts_isk = models.FloatField(default=0.0)
    sell_orders_isk = models.FloatField(default=0.0)
    total_isk_on_market = models.FloatField(default=0.0)

    contracts_synced_at = models.DateTimeField(null=True, blank=True)
    orders_synced_at = models.DateTimeField(null=True, blank=True)

    understocked_contracts = models.JSONField(default=list, blank=True)
    sell_gaps = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "EVE market ops monitor snapshot"
        verbose_name_plural = "EVE market ops monitor snapshots"
        indexes = [
            models.Index(
                fields=["location", "-captured_at"],
                name="market_ops_snap_loc_captured",
            ),
            models.Index(
                fields=["trigger", "-captured_at"],
                name="market_ops_snap_trig_captured",
            ),
        ]
        ordering = ["-captured_at"]

    def __str__(self):
        return (
            f"{self.location.location_name} {self.trigger} "
            f"@ {self.captured_at:%Y-%m-%d %H:%M}"
        )
