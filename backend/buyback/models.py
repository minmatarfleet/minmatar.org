from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from eveonline.models import EveCorporationContract, EveLocation

BUYBACK_CORPORATION_ID = 98838663
BUYBACK_CONTRACT_TYPE = "item_exchange"
BUYBACK_CORP_FALLBACK_NAME = "Minmatar Extraction Company"

# Amo - Minmatar Ore Reprocessing (contract destination / CorpDeliveries)
DEFAULT_STOCKPILE_STRUCTURE_ID = 1040765104287
# Corp office hangar under that structure (Director CorpSAG1)
DEFAULT_STOCKPILE_OFFICE_ID = 1055001268953
DEFAULT_STOCKPILE_HANGAR_FLAG = "CorpSAG1"

DEFAULT_ACCEPTED_CATEGORIES = [
    "Materials imported for recent industry supply-chain orders (full Jita buy)",
    "Other accepted ore and PI at surplus rate (90% Jita buy)",
]

DEFAULT_RATE_RULES = {
    "ore_refine": 0.85,
    "demand_jita_buy": 1.0,
    "surplus_jita_buy": 0.9,
}

DEFAULT_EXCLUSIONS: list[str] = []

DEFAULT_LEADING_TEXT = (
    "Alliance buyback by Minmatar Extraction Company. "
    "Paste your items for an instant offer, then contract your goods in Amo."
)

DEFAULT_DISCORD_THREAD_URL = (
    "https://discord.com/channels/1041384161505722368/1528803812599402577"
)

SELL_PRICE_BASIS_JITA_SPLIT = "jita_split"
SELL_PRICE_BASIS_JITA_BUY = "jita_buy"
SELL_PRICE_BASIS_JITA_SELL = "jita_sell"


class BuybackContractQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=["outstanding", "in_progress"])

    def finished(self):
        return self.filter(status="finished")


class BuybackContractManager(
    models.Manager.from_queryset(BuybackContractQuerySet)
):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                corporation__corporation_id=BUYBACK_CORPORATION_ID,
                type=BUYBACK_CONTRACT_TYPE,
                assignee_id=BUYBACK_CORPORATION_ID,
            )
        )


class BuybackContract(EveCorporationContract):
    """Proxy view over EveCorporationContract for M-EXC item-exchange buybacks."""

    objects = BuybackContractManager()

    class Meta:
        proxy = True


class SellPriceBasis(models.TextChoices):
    JITA_SPLIT = SELL_PRICE_BASIS_JITA_SPLIT, "Jita split"
    JITA_BUY = SELL_PRICE_BASIS_JITA_BUY, "Jita buy"
    JITA_SELL = SELL_PRICE_BASIS_JITA_SELL, "Jita sell"


def _default_accepted_categories():
    return list(DEFAULT_ACCEPTED_CATEGORIES)


def _default_rate_rules():
    return dict(DEFAULT_RATE_RULES)


def _default_exclusions():
    return list(DEFAULT_EXCLUSIONS)


class EveBuybackSettings(models.Model):
    """Singleton settings for the alliance buyback program (M-EXC)."""

    location = models.ForeignKey(
        EveLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buyback_settings",
    )
    assignee_name = models.CharField(
        max_length=255,
        default=BUYBACK_CORP_FALLBACK_NAME,
    )
    accepted_categories = models.JSONField(
        default=_default_accepted_categories,
        blank=True,
    )
    demand_jita_buy = models.FloatField(
        default=DEFAULT_RATE_RULES["demand_jita_buy"],
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Share of Jita buy paid for in-demand items (1.0 = 100%).",
    )
    surplus_jita_buy = models.FloatField(
        default=DEFAULT_RATE_RULES["surplus_jita_buy"],
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Share of Jita buy paid for surplus accepted items.",
    )
    ore_refine = models.FloatField(
        default=DEFAULT_RATE_RULES["ore_refine"],
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Assumed refine yield for compressed ore pricing.",
    )
    rate_rules = models.JSONField(
        default=_default_rate_rules,
        blank=True,
    )
    exclusions = models.JSONField(
        default=_default_exclusions,
        blank=True,
    )
    discord_thread_url = models.URLField(
        blank=True,
        default=DEFAULT_DISCORD_THREAD_URL,
    )
    leading_text = models.TextField(
        blank=True,
        default=DEFAULT_LEADING_TEXT,
    )
    active = models.BooleanField(default=True)
    stockpile_structure_id = models.BigIntegerField(
        default=DEFAULT_STOCKPILE_STRUCTURE_ID,
        help_text="Structure location_id for CorpDeliveries (Amo).",
    )
    stockpile_office_id = models.BigIntegerField(
        default=DEFAULT_STOCKPILE_OFFICE_ID,
        help_text="Office location_id for the kept-stock hangar.",
    )
    stockpile_hangar_flag = models.CharField(
        max_length=32,
        default=DEFAULT_STOCKPILE_HANGAR_FLAG,
        help_text="ESI location_flag for kept stock (e.g. CorpSAG1).",
    )
    stockpile_include_deliveries = models.BooleanField(
        default=True,
        help_text="Include CorpDeliveries at the structure in on-hand stock.",
    )
    sell_price_basis = models.CharField(
        max_length=16,
        choices=SellPriceBasis.choices,
        default=SellPriceBasis.JITA_SPLIT,
        help_text="Jita number used to price hangar sales to buyers.",
    )
    sell_markup = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Extra share on the sell basis (0 = none, 0.05 = 5%).",
    )
    coordinators = models.ManyToManyField(
        "auth.User",
        blank=True,
        related_name="buyback_coordinator_settings",
        help_text=(
            "Users who can see pending hangar sales and mark them complete "
            "on the site and in Discord."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Buyback settings"
        verbose_name_plural = "Buyback settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        self.rate_rules = {
            "ore_refine": float(self.ore_refine),
            "demand_jita_buy": float(self.demand_jita_buy),
            "surplus_jita_buy": float(self.surplus_jita_buy),
        }
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    def rates(self) -> dict[str, float]:
        return {
            "ore_refine": float(self.ore_refine),
            "demand_jita_buy": float(self.demand_jita_buy),
            "surplus_jita_buy": float(self.surplus_jita_buy),
        }

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Buyback settings (M-EXC)"


class BuybackAcceptedItem(models.Model):
    """Eve type accepted by the buyback program (appraisal allowlist)."""

    class Category(models.TextChoices):
        ORE = "ore", "Ore"
        P1 = "p1", "P1"
        P2 = "p2", "P2"
        P3 = "p3", "P3"
        P4 = "p4", "P4"

    class DemandStatus(models.TextChoices):
        SURPLUS = "surplus", "Surplus"
        LOW = "low", "Low"
        HIGH = "high", "High"

    eve_type = models.OneToOneField(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
        related_name="buyback_accepted_item",
    )
    active = models.BooleanField(default=True)
    category = models.CharField(
        max_length=16,
        choices=Category.choices,
    )
    demand_status = models.CharField(
        max_length=16,
        choices=DemandStatus.choices,
        default=DemandStatus.SURPLUS,
    )
    demand_quantity = models.BigIntegerField(default=0)
    stockpile_quantity = models.BigIntegerField(default=0)
    metrics_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Buyback accepted item"
        verbose_name_plural = "Buyback accepted items"
        ordering = ["category", "eve_type__name"]

    @property
    def in_demand(self) -> bool:
        return self.demand_status != self.DemandStatus.SURPLUS

    def __str__(self):
        status = "active" if self.active else "inactive"
        return f"{self.eve_type.name} ({self.category}, {status})"


class BuybackLedgerEntry(models.Model):
    """Material movement for the buyback stock ledger."""

    class Reason(models.TextChoices):
        IN_CONTRACT = "in_contract", "In (contract)"
        SOLD_ORDER = "sold_order", "Sold (sell order)"
        SOLD_CONTRACT = "sold_contract", "Sold (contract)"
        UNKNOWN = "unknown", "Unknown"

    reason = models.CharField(max_length=32, choices=Reason.choices)
    eve_type = models.ForeignKey(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
        related_name="buyback_ledger_entries",
    )
    quantity = models.BigIntegerField()
    occurred_at = models.DateTimeField()
    unit_price = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    isk_total = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    source_id = models.CharField(max_length=64)
    location_id = models.BigIntegerField(null=True, blank=True)
    counterparty_id = models.BigIntegerField(null=True, blank=True)
    counterparty_name = models.CharField(
        max_length=255, blank=True, default=""
    )
    counterparty_kind = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="character, corporation, or empty when unknown",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Buyback ledger entry"
        verbose_name_plural = "Buyback ledger entries"
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["reason", "source_id", "eve_type"],
                name="buyback_ledger_reason_source_type_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["occurred_at"]),
            models.Index(fields=["reason", "occurred_at"]),
        ]

    def __str__(self):
        return (
            f"{self.reason} {self.quantity}×{self.eve_type_id} "
            f"@ {self.occurred_at}"
        )


class BuybackHangarSnapshot(models.Model):
    """Point-in-time qty by type_id in tracked buyback hangars."""

    taken_at = models.DateTimeField(db_index=True)
    quantities = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Buyback hangar snapshot"
        verbose_name_plural = "Buyback hangar snapshots"
        ordering = ["-taken_at"]

    def __str__(self):
        return f"Hangar snapshot @ {self.taken_at}"


class BuybackPurchaseOrder(models.Model):
    """Pending or finished sale of buyback stock to a member."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Source(models.TextChoices):
        PLANNER = "planner", "Planner"
        STOCKPILE = "stockpile", "Stockpile"

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    source = models.CharField(
        max_length=16,
        choices=Source.choices,
        default=Source.STOCKPILE,
    )
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="buyback_purchase_orders",
    )
    character_id = models.BigIntegerField(null=True, blank=True)
    character_name = models.CharField(max_length=64, blank=True, default="")
    paste = models.TextField()
    contract_total = models.BigIntegerField()
    sell_price_basis = models.CharField(max_length=16)
    sell_markup = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buyback_purchase_orders_completed",
    )
    discord_thread_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Buyback purchase order"
        verbose_name_plural = "Buyback purchase orders"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["status", "-created_at"],
                name="buyback_po_status_created",
            ),
        ]

    def __str__(self):
        who = self.character_name or self.created_by_id
        return f"Purchase #{self.pk} {self.status} for {who}"


class BuybackPurchaseOrderLine(models.Model):
    """One hangar type on a buyback purchase order."""

    class FillSource(models.TextChoices):
        EXACT = "exact", "Exact"
        REFINE = "refine", "Refine"

    order = models.ForeignKey(
        BuybackPurchaseOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    eve_type = models.ForeignKey(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
        related_name="buyback_purchase_order_lines",
    )
    name = models.CharField(max_length=255)
    quantity = models.BigIntegerField()
    unit_price = models.DecimalField(max_digits=20, decimal_places=2)
    line_total = models.DecimalField(max_digits=20, decimal_places=2)
    fill_source = models.CharField(
        max_length=16,
        choices=FillSource.choices,
        default=FillSource.EXACT,
    )

    class Meta:
        verbose_name = "Buyback purchase order line"
        verbose_name_plural = "Buyback purchase order lines"
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.quantity}×{self.name}"
