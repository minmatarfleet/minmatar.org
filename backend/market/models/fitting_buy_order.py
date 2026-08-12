"""Personal-owned, globally visible fitting buy / Jita shopping orders."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from eveuniverse.models import EveType

from fittings.models import EveFitting


class FittingBuyOrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_FITTING = "pending_fitting", "Pending fitting"
    PURCHASED = "purchased", "Purchased"
    ARCHIVED = "archived", "Archived"


class FittingBuyJitaCheckStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETE = "complete", "Complete"
    FAILED = "failed", "Failed"


class FittingBuyOrder(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fitting_buy_orders",
    )
    status = models.CharField(
        max_length=16,
        choices=FittingBuyOrderStatus.choices,
        default=FittingBuyOrderStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField(blank=True, default="")
    stock_paste = models.TextField(
        blank=True,
        default="",
        help_text="Raw inventory / Multibuy paste applied against the BOM.",
    )
    include_hull = models.BooleanField(
        default=False,
        help_text="If false, hulls are excluded from the shopping list.",
    )
    jita_checked_at = models.DateTimeField(null=True, blank=True)
    shopping_allocations = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Buy splits for short types: "
            '{ "<preferred_type_id>": [{"type_id": int, "qty": int}, ...] }.'
        ),
    )
    variant_jita_cache = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Jita depth for short-item variants from the last check: "
            '{ "<type_id>": {"volume", "order_count", "sell_min"} }.'
        ),
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        verbose_name = "fitting buy order"
        verbose_name_plural = "fitting buy orders"

    def __str__(self):
        return f"Order #{self.pk} ({self.owner_id})"


class FittingBuyOrderLine(models.Model):
    order = models.ForeignKey(
        FittingBuyOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    fitting = models.ForeignKey(
        EveFitting,
        on_delete=models.PROTECT,
        related_name="fitting_buy_order_lines",
    )
    quantity = models.PositiveIntegerField(default=1)
    swaps = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "List of {preferred_type_id, substitute_type_id, notes?} applied "
            "to this line."
        ),
    )
    swap_hull_qty = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "When set with swaps, this many hulls use the swapped EFT; "
            "the rest keep the original fit. Null means all hulls are swapped."
        ),
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "fitting buy order line"
        verbose_name_plural = "fitting buy order lines"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "fitting"],
                name="unique_fitting_buy_order_fitting",
            ),
        ]

    def __str__(self):
        return f"{self.fitting_id} x{self.quantity} on order {self.order_id}"


class FittingBuyOrderItem(models.Model):
    order = models.ForeignKey(
        FittingBuyOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    eve_type = models.ForeignKey(
        EveType,
        on_delete=models.PROTECT,
        related_name="+",
    )
    needed_qty = models.PositiveIntegerField(default=0)
    stock_qty = models.PositiveIntegerField(default=0)
    buy_qty = models.PositiveIntegerField(default=0)
    jita_sell_volume = models.BigIntegerField(null=True, blank=True)
    jita_sell_min = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        null=True,
        blank=True,
    )
    jita_order_count = models.PositiveIntegerField(null=True, blank=True)
    unit_price = models.DecimalField(
        max_digits=32,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual landed unit price pasted by the owner.",
    )

    class Meta:
        ordering = ["eve_type__name"]
        verbose_name = "fitting buy order item"
        verbose_name_plural = "fitting buy order items"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "eve_type"],
                name="unique_fitting_buy_order_item_type",
            ),
        ]

    def __str__(self):
        return (
            f"{self.eve_type_id} buy {self.buy_qty} on order {self.order_id}"
        )

    @property
    def shortfall(self) -> int | None:
        if self.jita_sell_volume is None:
            return None
        return max(0, self.buy_qty - int(self.jita_sell_volume))


class FittingBuyJitaCheck(models.Model):
    order = models.ForeignKey(
        FittingBuyOrder,
        on_delete=models.CASCADE,
        related_name="jita_checks",
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    status = models.CharField(
        max_length=16,
        choices=FittingBuyJitaCheckStatus.choices,
        default=FittingBuyJitaCheckStatus.PENDING,
        db_index=True,
    )
    force_refresh = models.BooleanField(default=False)
    type_ids = models.JSONField(default=list, blank=True)
    done_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    results = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "fitting buy Jita check"
        verbose_name_plural = "fitting buy Jita checks"

    def __str__(self):
        return f"Jita check {self.pk} order {self.order_id} ({self.status})"
