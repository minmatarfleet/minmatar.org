from django.db import models


class TribeGroupActivity(models.Model):
    """
    Configuration row: defines which activity type a tribe group tracks.
    When processing runs, matching source events create TribeGroupActivityRecord rows.
    """

    KILLMAIL = "killmail"
    LOSSMAIL = "lossmail"
    FLEET_PARTICIPATION = "fleet_participation"
    MINING = "mining"
    PLANETARY_INTERACTION = "planetary_interaction"
    INDUSTRY = "industry"
    CONTRACT = "contract"
    COURIER_CONTRACT = "courier_contract"
    MARKET_ORDER = "market_order"

    ACTIVITY_TYPE_CHOICES = [
        (KILLMAIL, "Killmail"),
        (LOSSMAIL, "Lossmail"),
        (FLEET_PARTICIPATION, "Fleet participation"),
        (MINING, "Mining"),
        (PLANETARY_INTERACTION, "Planetary interaction"),
        (INDUSTRY, "Industry"),
        (CONTRACT, "Contract"),
        (COURIER_CONTRACT, "Courier contract"),
        (MARKET_ORDER, "Market order"),
    ]

    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="activities",
    )
    activity_type = models.CharField(
        max_length=64,
        choices=ACTIVITY_TYPE_CHOICES,
    )
    source_eve_type_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Filter on what the member was using: ship type for killmail/lossmail/fleet, "
            "ore type for mining, blueprint type for industry, item type for market. Null = any."
        ),
    )
    target_eve_type_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Filter on what was destroyed/targeted: victim's ship for killmail. "
            "Null = any. Not applicable for most activity types."
        ),
    )
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    points_per_record = models.FloatField(
        null=True,
        blank=True,
        help_text="Points awarded per record (count-based: killmail, fleet).",
    )
    points_per_unit = models.FloatField(
        null=True,
        blank=True,
        help_text="Points per unit of quantity (e.g. mining m³, industry ISK).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tribe_group} — {self.get_activity_type_display()}"

    class Meta:
        ordering = ["tribe_group", "activity_type"]
        verbose_name_plural = "Tribe group activities"
