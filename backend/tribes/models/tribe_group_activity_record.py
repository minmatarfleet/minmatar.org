from django.db import models


class TribeGroupActivityRecord(models.Model):
    """
    Event log: one row per occurrence of a tracked activity for a tribe member.
    Created by activity processors when source data (killmail, mining entry, etc.)
    matches an active TribeGroupActivity config.
    """

    tribe_group_activity = models.ForeignKey(
        "tribes.TribeGroupActivity",
        on_delete=models.CASCADE,
        related_name="records",
    )
    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tribe_activity_records",
        help_text="Acting character; may be null for fleet (bare character_id in source).",
    )
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tribe_activity_records",
        help_text="Denormalized from character for fast filtering.",
    )
    source_type_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text=(
            "EVE type ID of what the member was using (ship, ore, blueprint, item). "
            "Populated at processing time."
        ),
    )
    target_type_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="EVE type ID of what was destroyed/targeted (victim ship for killmails).",
    )
    quantity = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Numeric amount for quantifiable activities: units mined, ISK, runs, m³, etc. "
            "Null for killmail/lossmail/fleet (1 per record implicit)."
        ),
    )
    unit = models.CharField(
        max_length=32,
        blank=True,
        help_text='e.g. "units", "ISK", "runs", "m3". Empty for non-quantifiable types.',
    )
    reference_type = models.CharField(
        max_length=128,
        help_text="Source model name (e.g. EveCharacterKillmail, EveCharacterMiningEntry).",
    )
    reference_id = models.CharField(
        max_length=255,
        help_text="Source record PK for deduplication; composite string for mining entries.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tribe_group_activity} — {self.reference_type}:{self.reference_id}"

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "tribe_group_activity",
                    "reference_type",
                    "reference_id",
                ],
                name="tribes_tribegroupactivityrecord_unique_ref",
            )
        ]
        indexes = [
            models.Index(
                fields=["tribe_group_activity", "created_at"],
                name="tribes_tgarecord_act_created",
            ),
            models.Index(
                fields=["user", "created_at"],
                name="tribes_tgarecord_user_created",
            ),
        ]
