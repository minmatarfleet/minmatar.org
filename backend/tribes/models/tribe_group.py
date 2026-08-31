from django.db import models

from eveonline.scopes import TokenType


class TribeGroup(models.Model):
    """
    The actual joinable unit within a tribe.
    A single-focus tribe (e.g. Mining) has one TribeGroup.
    A multi-focus tribe (e.g. Capitals) has several (Dreads, Carriers, Fax).
    """

    TOKEN_TYPE_CHOICES = [
        (t.value, t.value) for t in TokenType if t != TokenType.PUBLIC
    ]

    tribe = models.ForeignKey(
        "tribes.Tribe", on_delete=models.CASCADE, related_name="groups"
    )
    name = models.CharField(max_length=128)
    code = models.CharField(
        max_length=64,
        unique=True,
        help_text="Stable catalog key for reports and bindings (e.g. supply.mining).",
    )
    description = models.TextField(blank=True)
    content = models.TextField(
        blank=True,
        help_text="Markdown-formatted long-form description for the group hub.",
    )
    group = models.OneToOneField(
        "auth.Group",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tribe_group",
        help_text="Group-level Discord role (e.g. 'Dreads').",
    )
    chief = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="led_tribe_groups",
        help_text="Group leader; can approve/deny membership for this group.",
    )
    discord_channel_id = models.BigIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    required_token_type = models.CharField(
        max_length=40,
        blank=True,
        default="",
        choices=TOKEN_TYPE_CHOICES,
        help_text=(
            "If set, characters must have this ESI token type to apply or be added."
        ),
    )
    require_off_trial = models.BooleanField(
        default=False,
        help_text=(
            "If set, applicants must be off Alliance trial (community status "
            "active) before they can apply."
        ),
    )
    allowed_affiliations = models.ManyToManyField(
        "groups.AffiliationType",
        blank=True,
        related_name="tribe_groups",
        help_text=(
            "Affiliations that may apply to this group. "
            "Empty uses the tribes.apply PilotFeature affiliations "
            "(currently Alliance and Associate)."
        ),
    )

    def save(self, *args, **kwargs):
        if not self.code:
            # pylint: disable=import-outside-toplevel
            from tribes.helpers.group_code import (
                ensure_unique_tribe_group_code,
            )

            ensure_unique_tribe_group_code(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tribe.name} — {self.name}"

    class Meta:
        ordering = ["tribe__name", "name"]
        unique_together = [("tribe", "name")]
