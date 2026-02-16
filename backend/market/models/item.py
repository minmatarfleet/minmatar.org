from django.db import models
from django.db.models import Exists, OuterRef, Sum
from django.utils import timezone

from eveuniverse.models import EveType
from eveonline.models import EveLocation


class EveTypeWithSellOrdersManager(models.Manager):
    """Return only EveTypes that have at least one EveMarketItemOrder."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                Exists(
                    EveMarketItemOrder.objects.filter(item_id=OuterRef("pk"))
                )
            )
        )


class EveTypeWithSellOrders(EveType):
    """
    Proxy for EveType limited to types we have sell orders for.
    Used in admin as the "Market sell orders" entry point.
    """

    class Meta:
        proxy = True
        verbose_name = "EVE type (with sell orders)"
        verbose_name_plural = "EVE types (with sell orders)"

    objects = EveTypeWithSellOrdersManager()


class EveMarketItemExpectation(models.Model):
    """
    Seed definition: track a target quantity of an EVE type (e.g. 1000 missiles)
    at a location, measured by current sell orders.
    """

    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.RESTRICT)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return str(f"{self.item.name} - {self.location.location_name}")

    @property
    def current_quantity(self):
        """Total quantity on sell orders for this item at this location."""
        result = EveMarketItemOrder.objects.filter(
            item=self.item,
            location=self.location,
        ).aggregate(total=Sum("quantity"))
        return result["total"] or 0

    @property
    def desired_quantity(self):
        return self.quantity

    @property
    def is_fulfilled(self):
        return self.current_quantity >= self.desired_quantity

    @property
    def is_understocked(self):
        understocked_percentage = 0.5
        return (
            self.current_quantity
            < self.desired_quantity * understocked_percentage
        )


class EveMarketItemResponsibility(models.Model):
    expectation = models.ForeignKey(
        EveMarketItemExpectation, on_delete=models.CASCADE
    )
    # character or corporation
    entity_id = models.BigIntegerField()

    def __str__(self):
        return str(f"{self.entity_id} - {self.expectation.item.name}")


class EveMarketItemOrder(models.Model):
    """One row per market order; order_id from ESI (when present) avoids duplicate imports."""

    order_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text="ESI order_id when returned by structure markets; prevents duplicate imports.",
    )
    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    quantity = models.IntegerField()
    issuer_external_id = models.BigIntegerField(null=True, blank=True)
    imported_by_task_uid = models.CharField(
        max_length=64, null=True, blank=True
    )
    imported_page = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="1-based ESI page this order was imported from (for debugging).",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(
                fields=["location", "imported_by_task_uid"],
                name="market_itemorder_loc_task",
            ),
            models.Index(
                fields=["location", "item"],
                name="market_itemorder_loc_item",
            ),
        ]

    def __str__(self):
        return str(f"{self.item.name} - {self.location.location_name}")


class EveMarketItemTransaction(models.Model):
    item = models.ForeignKey(EveType, on_delete=models.CASCADE)
    location = models.ForeignKey(EveLocation, on_delete=models.RESTRICT)
    price = models.DecimalField(max_digits=32, decimal_places=2)
    quantity = models.IntegerField()
    issuer_external_id = models.BigIntegerField()
    sell_date = models.DateTimeField()

    def __str__(self):
        return str(f"{self.item.name} - {self.location.location_name}")
