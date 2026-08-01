from django.db import models

from eveonline.models import EveCorporationContract, EveLocation

BUYBACK_CORPORATION_ID = 98838663
BUYBACK_CONTRACT_TYPE = "item_exchange"
BUYBACK_CORP_FALLBACK_NAME = "Minmatar Extraction Company"

DEFAULT_ACCEPTED_CATEGORIES = [
    "Compressed highsec ore",
    "PI used in recent production",
]

DEFAULT_RATE_RULES = {
    "ore_refine": 0.85,
    "ore_jita_buy": 1.0,
    "p1_jita_buy_cap": 0.9,
    # P2+ (and other accepted non-ore, non-P1)
    "other_jita_buy": 1.0,
}

DEFAULT_EXCLUSIONS: list[str] = []

DEFAULT_LEADING_TEXT = (
    "Alliance buyback via Minmatar Extraction Company. "
    "Paste your items for an instant offer, then contract "
    "compressed highsec ore and PI at Amo — paid within ~24 hours."
)

DEFAULT_DISCORD_THREAD_URL = (
    "https://discord.com/channels/1041384161505722368/1528803812599402577"
)


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
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Buyback settings"
        verbose_name_plural = "Buyback settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Buyback accepted item"
        verbose_name_plural = "Buyback accepted items"
        ordering = ["category", "eve_type__name"]

    def __str__(self):
        status = "active" if self.active else "inactive"
        return f"{self.eve_type.name} ({self.category}, {status})"
