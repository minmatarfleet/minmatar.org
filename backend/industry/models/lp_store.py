from django.conf import settings
from django.db import models
from django.utils import timezone


class IndustryLoyaltyPoint(models.Model):
    """
    A loyalty-point currency we care about (e.g. Tribal Liberation Force).

    Holds default ISK/LP pricing for the industry planner. Contacts who can
    supply this LP are linked via IndustryLoyaltyPointContact.
    """

    name = models.CharField(max_length=128)
    corporation_id = models.BigIntegerField(
        unique=True,
        help_text="ESI NPC corporation ID for this LP store (e.g. TLIB 1000182).",
    )
    default_isk_per_lp = models.PositiveIntegerField(
        default=800,
        help_text="Default ISK per LP used when planning navy BPC costs.",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Industry loyalty point"
        verbose_name_plural = "Industry loyalty points"

    def __str__(self) -> str:
        return f"{self.name} ({self.default_isk_per_lp} ISK/LP)"


class IndustryLoyaltyPointContact(models.Model):
    """Someone to contact for a given loyalty-point currency."""

    loyalty_point = models.ForeignKey(
        IndustryLoyaltyPoint,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    character_name = models.CharField(max_length=64)
    eve_character = models.ForeignKey(
        "eveonline.EveCharacter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loyalty_point_contacts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loyalty_point_contacts",
    )
    discord_user_id = models.BigIntegerField(null=True, blank=True)
    discord_username = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["loyalty_point__name", "character_name"]
        verbose_name = "Industry loyalty point contact"
        verbose_name_plural = "Industry loyalty point contacts"

    def __str__(self) -> str:
        return f"{self.character_name} ({self.loyalty_point.name})"


class IndustryLpStoreOffer(models.Model):
    """
    Cached pure LP+ISK loyalty-store offers (no required items).

    Populated when navy/faction industry products are saved, or on first
    planner miss / manual sync. Not polled on a schedule.
    """

    offer_id = models.BigIntegerField(primary_key=True)
    corporation_id = models.BigIntegerField(db_index=True)
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
