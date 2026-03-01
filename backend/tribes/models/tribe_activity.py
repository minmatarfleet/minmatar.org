from django.db import models


class TribeActivity(models.Model):
    """
    Records raw output for a TribeGroup member. No points — displayed as raw quantities.
    Ingested automatically from ESI or manually logged by chiefs/elders.
    """

    ACTIVITY_FLEET_PARTICIPATION = "fleet_participation"
    ACTIVITY_KILLS = "kills"
    ACTIVITY_LOSSES = "losses"
    ACTIVITY_MINING = "mining_contribution"
    ACTIVITY_FREIGHT = "freight_contribution"
    ACTIVITY_INDUSTRY = "industry_job_completed"
    ACTIVITY_CONTENT = "content_contribution"
    ACTIVITY_DOCTRINE = "doctrine_update"
    ACTIVITY_FITTING = "fitting_update"
    ACTIVITY_CUSTOM = "custom"
    ACTIVITY_TYPE_CHOICES = [
        (ACTIVITY_FLEET_PARTICIPATION, "Fleet Participation"),
        (ACTIVITY_KILLS, "Kills"),
        (ACTIVITY_LOSSES, "Losses"),
        (ACTIVITY_MINING, "Mining Contribution"),
        (ACTIVITY_FREIGHT, "Freight Contribution"),
        (ACTIVITY_INDUSTRY, "Industry Job Completed"),
        (ACTIVITY_CONTENT, "Content Contribution"),
        (ACTIVITY_DOCTRINE, "Doctrine Update"),
        (ACTIVITY_FITTING, "Fitting Update"),
        (ACTIVITY_CUSTOM, "Custom"),
    ]

    tribe_group = models.ForeignKey(
        "tribes.TribeGroup",
        on_delete=models.CASCADE,
        related_name="activities",
    )
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="tribe_activities",
        help_text="Denormalised from character for query convenience.",
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tribe_activities",
        help_text="Acting character; null for manually logged activities.",
    )
    activity_type = models.CharField(
        max_length=32, choices=ACTIVITY_TYPE_CHOICES
    )
    quantity = models.FloatField(
        help_text="Raw output number (m³, ISK, ships, etc.)."
    )
    unit = models.CharField(
        max_length=16, help_text="E.g. 'm3', 'ISK', 'kills', 'fleets'."
    )
    description = models.CharField(max_length=255, blank=True)
    reference_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Source record ID for deduplication (e.g. killmail_id, job_id).",
    )
    reference_type = models.CharField(
        max_length=64,
        blank=True,
        help_text="Source model name (e.g. 'EveCharacterKillmail', 'EveCharacterIndustryJob').",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.user} — {self.activity_type} ({self.quantity} {self.unit})"
        )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tribe_group", "activity_type"]),
            models.Index(fields=["reference_type", "reference_id"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["reference_type", "reference_id"],
                condition=~models.Q(reference_id=""),
                name="tribes_tribeactivity_unique_reference",
            )
        ]
