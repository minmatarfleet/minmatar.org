"""Faction Warfare LP payout notifications.

The militia corporation sends a character notification for every LP payout:
complex captures, advantage sites, supply caches, battlefields and kills.
ESI has no site-completion endpoint, so these notifications are the only
per-pilot record that a pilot ran a site. See
``docs/campaigns/fw-campaigns-plan.md`` section 5.
"""

from __future__ import annotations

from django.db import models


class FwPayoutEventCode(models.Model):
    """Calibration table mapping a payout ``event`` code to a site kind.

    Seeded with the codes observed in a live pull, all marked unconfirmed.
    Unconfirmed codes are stored and displayed but never scored, and unknown
    codes surface in the admin for a human to tag.
    """

    event_code = models.IntegerField(unique=True, db_index=True)
    site_kind = models.CharField(
        max_length=24,
        default="unknown",
        help_text="Matches campaigns.models.SiteKind values.",
    )
    label = models.CharField(max_length=64, blank=True, default="")
    amount_rule = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="How the LP amount is derived, for humans.",
    )
    confirmed = models.BooleanField(
        default=False,
        help_text="Unconfirmed codes are never scored.",
    )
    confirmed_by = models.CharField(max_length=255, blank=True, default="")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["event_code"]
        verbose_name = "FW payout event code"

    def __str__(self) -> str:
        state = "confirmed" if self.confirmed else "unconfirmed"
        return f"{self.event_code} → {self.site_kind} ({state})"


class EveCharacterFwLpPayout(models.Model):
    """One ``FacWarLPPayout*`` notification, stored once per notification id."""

    character = models.ForeignKey(
        "eveonline.EveCharacter",
        on_delete=models.CASCADE,
        related_name="fw_lp_payouts",
    )
    notification_id = models.BigIntegerField(unique=True, db_index=True)
    notification_type = models.CharField(max_length=64)
    occurred_at = models.DateTimeField(db_index=True)

    amount_lp = models.IntegerField(default=0)
    corp_id = models.BigIntegerField(null=True, blank=True)
    event_code = models.IntegerField(null=True, blank=True, db_index=True)
    location_id = models.BigIntegerField(
        null=True, blank=True, db_index=True, help_text="Solar system id."
    )
    ref_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="itemRefID: the site instance for a complex, or the "
        "killmail id for a kill payout.",
    )
    char_ref_id = models.BigIntegerField(null=True, blank=True)
    disqualification_type = models.CharField(
        max_length=64, blank=True, default=""
    )
    raw_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "FW LP payout"
        indexes = [
            models.Index(fields=["character", "-occurred_at"]),
            models.Index(fields=["location_id", "-occurred_at"]),
            models.Index(fields=["event_code", "ref_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.character_id} {self.event_code} {self.amount_lp} LP"

    @property
    def is_kill_payout(self) -> bool:
        return self.notification_type.endswith("Kill")
