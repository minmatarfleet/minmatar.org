from django.conf import settings
from django.db import models
from django.utils import timezone


class IndustryLoyaltyPoint(models.Model):
    """
    A loyalty-point currency we care about (e.g. Tribal Liberation Force).

    Holds default ISK/LP pricing for the industry planner. Holders (sellers /
    stockpiles) and contacts are linked via IndustryLoyaltyPointAccount.
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


class IndustryLoyaltyPointAccount(models.Model):
    """
    A holder of one LP currency: external seller or in-alliance stockpile.

    Balance is derived from ledger entries (SUM of amounts). Offer price is
    the current ask; each ledger row carries its own lot price (825, 850, …).
    """

    class Role(models.TextChoices):
        SELLER = "seller", "Seller"
        STOCKPILE = "stockpile", "Stockpile"

    loyalty_point = models.ForeignKey(
        IndustryLoyaltyPoint,
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    name = models.CharField(max_length=128)
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.SELLER,
        db_index=True,
    )
    isk_per_lp = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Current offer ISK/LP for this holder. Falls back to the currency "
            "default when empty. Lot history uses each ledger entry's price."
        ),
    )
    eve_character = models.ForeignKey(
        "eveonline.EveCharacter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loyalty_point_accounts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loyalty_point_accounts",
    )
    corporation_name = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["loyalty_point__name", "name"]
        verbose_name = "Industry loyalty point account"
        verbose_name_plural = "Industry loyalty point accounts"
        constraints = [
            models.UniqueConstraint(
                fields=["loyalty_point", "name"],
                condition=models.Q(is_active=True),
                name="uniq_active_lp_account_name_per_currency",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.loyalty_point.name}, {self.role})"


class IndustryLoyaltyPointContact(models.Model):
    """Someone to contact for a given LP account (seller or stockpile)."""

    account = models.ForeignKey(
        IndustryLoyaltyPointAccount,
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
        ordering = ["account__loyalty_point__name", "character_name"]
        verbose_name = "Industry loyalty point contact"
        verbose_name_plural = "Industry loyalty point contacts"

    def __str__(self) -> str:
        return f"{self.character_name} ({self.account.name})"


class IndustryLoyaltyPointLedgerEntry(models.Model):
    """
    One credit/debit lot against an LP account.

    Credits are intakes at a specific ISK/LP (e.g. +200k @ 825). Debits are
    draws. Mixed prices on the same account are expected.
    """

    account = models.ForeignKey(
        IndustryLoyaltyPointAccount,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    amount = models.BigIntegerField(
        help_text="Signed LP change: positive credit, negative debit.",
    )
    isk_per_lp = models.PositiveIntegerField(
        help_text="ISK/LP for this lot (required; e.g. 825 or 850).",
    )
    notes = models.TextField(blank=True)
    balance_after = models.BigIntegerField(
        help_text="Account balance after this entry was posted.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loyalty_point_ledger_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Industry loyalty point ledger entry"
        verbose_name_plural = "Industry loyalty point ledger entries"

    def __str__(self) -> str:
        sign = "+" if self.amount >= 0 else ""
        return (
            f"{self.account.name}: {sign}{self.amount} LP "
            f"@ {self.isk_per_lp} ISK/LP"
        )


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
