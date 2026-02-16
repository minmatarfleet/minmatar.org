from django.db import models


class IndustryOrder(models.Model):
    """An industry order: a list of Eve types and quantities to build."""

    created_at = models.DateTimeField(auto_now_add=True)
    needed_by = models.DateField()
    fulfilled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this order was marked as fulfilled.",
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="industry_orders",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} ({self.character.character_name}, needed by {self.needed_by})"


class IndustryOrderItem(models.Model):
    """One line in an order: a quantity of a single Eve type."""

    order = models.ForeignKey(
        IndustryOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    eve_type = models.ForeignKey(
        "eveuniverse.EveType",
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]
        unique_together = [["order", "eve_type"]]

    def __str__(self):
        return f"{self.order}: {self.eve_type.name} x{self.quantity}"


class IndustryOrderItemAssignment(models.Model):
    """Assignment of part of an order item to a character to build."""

    order_item = models.ForeignKey(
        IndustryOrderItem,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="industry_order_assignments",
    )
    quantity = models.PositiveIntegerField(
        help_text="Quantity of this item assigned to this character to build.",
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.order_item} → {self.character.character_name} x{self.quantity}"
