from django.db import models
from django.utils import timezone


class IndustryLpStoreOffer(models.Model):
    """
    Cached pure LP+ISK loyalty-store offers (no required items).

    Populated by Celery from GET /loyalty/stores/{corporation_id}/offers/
    for the four FW militia corps. Planner navy-BPC costing reads this
    table instead of calling ESI per request.
    """

    offer_id = models.BigIntegerField(primary_key=True)
    corporation_id = models.BigIntegerField()
    type_id = models.BigIntegerField(db_index=True)
    lp_cost = models.PositiveIntegerField()
    isk_cost = models.BigIntegerField()
    quantity = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Industry LP store offer"
        verbose_name_plural = "Industry LP store offers"

    def __str__(self) -> str:
        return (
            f"offer {self.offer_id}: type={self.type_id} "
            f"lp={self.lp_cost} isk={self.isk_cost} qty={self.quantity}"
        )
