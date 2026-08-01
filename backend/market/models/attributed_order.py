from django.db import models
from django.utils import timezone


class EveMarketAttributedOrder(models.Model):
    """Personal or corp open order; owner_character_id is lister or ESI issued_by."""

    order_id = models.BigIntegerField(unique=True)
    type_id = models.IntegerField()
    location_esi_id = models.BigIntegerField(db_index=True)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    volume_remain = models.IntegerField()
    is_buy_order = models.BooleanField(default=False)
    issued = models.DateTimeField(null=True, blank=True)
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    owner_character_id = models.BigIntegerField(db_index=True)
    corporation_id = models.BigIntegerField(
        null=True, blank=True, db_index=True
    )
    synced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(
                fields=["owner_character_id", "is_buy_order"],
                name="market_attrorder_owner_buy",
            ),
            models.Index(
                fields=["location_esi_id", "is_buy_order"],
                name="market_attrorder_loc_buy",
            ),
        ]

    def __str__(self):
        return f"order {self.order_id} char {self.owner_character_id}"
