from datetime import datetime as dt_datetime, time as dt_time

from django.db import models
from django.utils import timezone

from eveonline.models import EveCharacterIndustryJob


class IndustryOrder(models.Model):
    """An industry order: a list of Eve types and quantities to build."""

    created_at = models.DateTimeField(auto_now_add=True)
    needed_by = models.DateField()
    fulfilled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this order was marked as fulfilled.",
    )
    public_short_code = models.CharField(
        max_length=3,
        db_index=True,
        help_text="3-character public code (Discord); unique among active (unfulfilled) orders.",
    )
    contract_to = models.CharField(
        max_length=255,
        blank=True,
        help_text="Contract recipient name (character or corporation), free text.",
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="industry_orders",
    )
    location = models.ForeignKey(
        "eveonline.EveLocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="industry_orders",
        help_text="Station or structure where the order should be built/delivered.",
    )
    tribe_groups = models.ManyToManyField(
        "tribes.TribeGroup",
        blank=True,
        related_name="industry_orders",
        help_text="Tribe groups this order belongs to (reporting, town hall).",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} ({self.character.character_name}, needed by {self.needed_by})"

    def _order_period_end(self):
        """End of the order's relevant time period (needed_by EOD or fulfilled_at)."""
        if self.fulfilled_at is not None:
            return self.fulfilled_at
        end_of_day = timezone.make_aware(
            dt_datetime.combine(self.needed_by, dt_time.max)
        )
        return end_of_day

    def relevant_industry_jobs(self):
        """
        Industry jobs for this order's characters (owner + assignees) that
        overlap the order period: created_at through needed_by (or fulfilled_at).
        Includes in-progress and completed jobs in that window.
        """
        character_ids = {self.character_id}
        for item in self.items.prefetch_related("assignments").all():
            for assignment in item.assignments.all():
                character_ids.add(assignment.character_id)
        if not character_ids:
            return EveCharacterIndustryJob.objects.none()
        period_start = self.created_at
        period_end = self._order_period_end()
        return (
            EveCharacterIndustryJob.objects.filter(
                character_id__in=character_ids,
                end_date__gte=period_start,
                start_date__lte=period_end,
            )
            .select_related("character")
            .order_by("-end_date")
        )


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
    self_assign_maximum = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Per-character assignment cap for the first 48 hours after the order was "
            "created; after that window, only total line quantity limits assignments."
        ),
    )
    target_unit_price = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target unit price (ISK) for this line; shown on the public order list.",
    )
    target_estimated_margin = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target estimated margin (ISK) for this line; shown on the public order list.",
    )

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
    target_unit_price = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target unit price (ISK); set in admin.",
    )
    target_estimated_margin = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target estimated margin (ISK); set in admin.",
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this assignment was marked delivered.",
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.order_item} → {self.character.character_name} x{self.quantity}"
