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

    # Ephemeral: set by admin before save so price history records the actor.
    history_changed_by = None

    class Meta:
        ordering = ["name"]
        verbose_name = "Industry loyalty point"
        verbose_name_plural = "Industry loyalty points"

    def __str__(self) -> str:
        return f"{self.name} ({self.default_isk_per_lp} ISK/LP)"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        track_price = (
            update_fields is None or "default_isk_per_lp" in update_fields
        )
        previous = None
        had_previous = False
        if track_price and self.pk:
            try:
                previous = IndustryLoyaltyPoint.objects.values_list(
                    "default_isk_per_lp", flat=True
                ).get(pk=self.pk)
                had_previous = True
            except IndustryLoyaltyPoint.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        if not track_price or not had_previous:
            return
        if previous == self.default_isk_per_lp:
            return
        IndustryLoyaltyPointPriceHistory.objects.create(
            loyalty_point=self,
            account=None,
            old_isk_per_lp=previous,
            new_isk_per_lp=self.default_isk_per_lp,
            changed_by=self.history_changed_by,
        )


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

    # Ephemeral: set by admin before save so price history records the actor.
    history_changed_by = None

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

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        track_price = update_fields is None or "isk_per_lp" in update_fields
        previous = None
        had_previous = False
        if track_price and self.pk:
            try:
                previous = IndustryLoyaltyPointAccount.objects.values_list(
                    "isk_per_lp", flat=True
                ).get(pk=self.pk)
                had_previous = True
            except IndustryLoyaltyPointAccount.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        if not track_price or not had_previous:
            return
        if previous == self.isk_per_lp:
            return
        IndustryLoyaltyPointPriceHistory.objects.create(
            loyalty_point=self.loyalty_point,
            account=self,
            old_isk_per_lp=previous,
            new_isk_per_lp=self.isk_per_lp,
            changed_by=self.history_changed_by,
        )


class IndustryLoyaltyPointPriceHistory(models.Model):
    """
    Append-only log of ISK/LP price changes for currencies and account offers.

    Currency default changes have account=null. Account offer changes set both
    loyalty_point and account.
    """

    loyalty_point = models.ForeignKey(
        IndustryLoyaltyPoint,
        on_delete=models.CASCADE,
        related_name="price_history",
    )
    account = models.ForeignKey(
        IndustryLoyaltyPointAccount,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="price_history",
        help_text=(
            "Empty for published currency default rate changes; set for "
            "account offer price changes."
        ),
    )
    old_isk_per_lp = models.PositiveIntegerField(null=True, blank=True)
    new_isk_per_lp = models.PositiveIntegerField(null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loyalty_point_price_changes",
    )

    class Meta:
        ordering = ["-changed_at", "-id"]
        verbose_name = "Industry loyalty point price history"
        verbose_name_plural = "Industry loyalty point price histories"

    def __str__(self) -> str:
        scope = (
            self.account.name if self.account_id else self.loyalty_point.name
        )
        return (
            f"{scope}: {self.old_isk_per_lp} → {self.new_isk_per_lp} "
            f"ISK/LP at {self.changed_at}"
        )


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

    Market sell completions post a single stockpile credit (alliance inventory
    in) with seller + counterparty fields rather than dual account transfers —
    sell-order pilots often have no IndustryLoyaltyPointAccount row.
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
    market_order = models.ForeignKey(
        "IndustryLoyaltyPointMarketOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        help_text="Buyback market order that produced this entry, if any.",
    )
    seller_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loyalty_point_ledger_entries_as_seller",
        help_text="Pilot who sold LP (market order creator).",
    )
    seller_character_name = models.CharField(max_length=64, blank=True)
    counterparty_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loyalty_point_ledger_entries_as_counterparty",
        help_text="Other side of the trade (claimer / Conversion Team).",
    )
    counterparty_character_name = models.CharField(
        max_length=64,
        blank=True,
        help_text="Destination / receiving character when known.",
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
    Cached ESI loyalty-store offers (including required-item offers).

    Populated on Celery beat, navy/faction product save, planner miss, or
    manual admin sync. ESI reuses offer_id across militia corps, so identity
    is (corporation_id, offer_id).
    """

    offer_id = models.BigIntegerField()
    corporation_id = models.BigIntegerField(db_index=True)
    type_id = models.BigIntegerField(db_index=True)
    lp_cost = models.PositiveIntegerField()
    isk_cost = models.BigIntegerField()
    ak_cost = models.BigIntegerField(
        default=0,
        help_text="ESI ak_cost (EverMarks / alliance points); 0 when unused.",
    )
    quantity = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Industry LP store offer"
        verbose_name_plural = "Industry LP store offers"
        constraints = [
            models.UniqueConstraint(
                fields=["corporation_id", "offer_id"],
                name="uniq_lp_store_offer_corp_offer",
            ),
        ]
        indexes = [
            models.Index(
                fields=["corporation_id", "type_id"],
                name="industry_lp_offer_corp_type",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"offer {self.offer_id} corp={self.corporation_id}: "
            f"type={self.type_id} lp={self.lp_cost} isk={self.isk_cost} "
            f"qty={self.quantity}"
        )


class IndustryLpStoreOfferEconomics(models.Model):
    """
    Hourly rebuild of LP store offer market economics for the public catalog.

    Built from cached ESI offers + local Jita/Forge prices (no ESI call).
    Public offers API reads this table only.
    """

    offer = models.OneToOneField(
        IndustryLpStoreOffer,
        on_delete=models.CASCADE,
        related_name="economics_row",
        primary_key=True,
    )
    esi_offer_id = models.BigIntegerField(db_index=True)
    corporation_id = models.BigIntegerField(db_index=True)
    type_id = models.BigIntegerField(db_index=True)
    type_name = models.CharField(max_length=255, db_index=True)
    currency_name = models.CharField(max_length=128, blank=True, default="")
    kind = models.CharField(max_length=32, blank=True, default="")
    lp_cost = models.PositiveIntegerField()
    isk_cost = models.BigIntegerField()
    ak_cost = models.BigIntegerField(default=0)
    quantity = models.PositiveIntegerField(default=1)
    required_items_summary = models.CharField(
        max_length=512, blank=True, default=""
    )
    other_cost = models.BigIntegerField(null=True, blank=True)
    input_cost_isk = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="ISK cost + required items + Amamake mfg (no alliance freight).",
    )
    input_freight_isk = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Red Frog value freight on required items + materials.",
    )
    jita_sell = models.BigIntegerField(null=True, blank=True)
    jita_buy = models.BigIntegerField(null=True, blank=True)
    jita_avg_7d = models.BigIntegerField(null=True, blank=True)
    conversion_isk_per_lp_sell = models.FloatField(null=True, blank=True)
    conversion_isk_per_lp_buy = models.FloatField(null=True, blank=True)
    conversion_isk_per_lp_avg_7d = models.FloatField(null=True, blank=True)
    volume_1d = models.BigIntegerField(null=True, blank=True)
    volume_7d = models.BigIntegerField(null=True, blank=True)
    volume_30d = models.BigIntegerField(null=True, blank=True)
    involves_tag = models.BooleanField(default=False, db_index=True)
    involves_supply_package = models.BooleanField(default=False, db_index=True)
    involves_chip = models.BooleanField(default=False, db_index=True)
    involves_skin = models.BooleanField(default=False, db_index=True)
    is_useless = models.BooleanField(default=False, db_index=True)
    is_below_set_lp_price = models.BooleanField(default=False, db_index=True)
    is_below_set_lp_price_buy = models.BooleanField(
        default=False, db_index=True
    )
    is_below_set_lp_price_avg_7d = models.BooleanField(
        default=False, db_index=True
    )
    offer_updated_at = models.DateTimeField()
    rebuilt_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Industry LP store offer economics"
        verbose_name_plural = "Industry LP store offer economics"
        indexes = [
            models.Index(
                fields=["corporation_id", "-conversion_isk_per_lp_sell"],
                name="industry_lp_econ_corp_conv",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"econ offer={self.esi_offer_id} corp={self.corporation_id} "
            f"{self.type_name}"
        )


class IndustryLpStoreOfferRequiredItem(models.Model):
    """One required input item for an LP store offer."""

    offer = models.ForeignKey(
        IndustryLpStoreOffer,
        on_delete=models.CASCADE,
        related_name="required_items",
    )
    type_id = models.BigIntegerField(db_index=True)
    quantity = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Industry LP store offer required item"
        verbose_name_plural = "Industry LP store offer required items"
        constraints = [
            models.UniqueConstraint(
                fields=["offer", "type_id"],
                name="uniq_lp_store_offer_req_type",
            ),
        ]

    def __str__(self) -> str:
        return f"offer {self.offer_id}: type={self.type_id} x{self.quantity}"


class IndustryLoyaltyPointMarketOrder(models.Model):
    """Buy or sell offer for a loyalty-point currency (site LP buyback book)."""

    class Side(models.TextChoices):
        BUY = "buy", "Buy"
        SELL = "sell", "Sell"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLAIMED = "claimed", "Claimed"
        AWAITING_LP = "awaiting_lp", "Awaiting LP"
        AWAITING_ISK = "awaiting_isk", "Awaiting ISK"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    loyalty_point = models.ForeignKey(
        IndustryLoyaltyPoint,
        on_delete=models.CASCADE,
        related_name="market_orders",
    )
    side = models.CharField(max_length=8, choices=Side.choices, db_index=True)
    quantity = models.BigIntegerField()
    isk_per_lp = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty_point_market_orders_created",
    )
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loyalty_point_market_orders_claimed",
    )
    destination_character_name = models.CharField(max_length=64, blank=True)
    discord_thread_id = models.BigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Industry loyalty point market order"
        verbose_name_plural = "Industry loyalty point market orders"
        indexes = [
            models.Index(
                fields=["status", "side", "-created_at"],
                name="industry_lp_mkt_status_side",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.side.upper()} {self.quantity:,} "
            f"{self.loyalty_point.name} @ {self.isk_per_lp} "
            f"({self.status})"
        )


class IndustryLoyaltyPointMarketOrderClaim(models.Model):
    """Partial or full claim against an open LP market order."""

    order = models.ForeignKey(
        IndustryLoyaltyPointMarketOrder,
        on_delete=models.CASCADE,
        related_name="claims",
    )
    amount = models.BigIntegerField(
        help_text="LP quantity claimed in this fill.",
    )
    destination_character_name = models.CharField(max_length=64, blank=True)
    destination_corporation_name = models.CharField(max_length=128, blank=True)
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty_point_market_order_claims",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "Industry loyalty point market order claim"
        verbose_name_plural = "Industry loyalty point market order claims"

    def __str__(self) -> str:
        return (
            f"Claim {self.amount:,} on order {self.order_id} "
            f"by {self.claimed_by_id}"
        )
