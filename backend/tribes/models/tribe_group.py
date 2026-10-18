from django.db import models

from eveonline.scopes import TokenType


class TribeGroup(models.Model):
    """
    The actual joinable unit within a tribe.
    A single-focus tribe (e.g. Mining) has one TribeGroup.
    A multi-focus tribe (e.g. Capitals) has several (Dreads, Carriers, Fax).
    """

    # Who may publish posts, fleets or events as the group. Chiefs (anyone
    # who can manage the group) always can.
    POLICY_CHIEFS = "chiefs"
    POLICY_CHOSEN = "chosen"
    POLICY_MEMBERS = "members"
    POLICY_CHOICES = [
        (POLICY_CHIEFS, "Chiefs only"),
        (POLICY_CHOSEN, "Chiefs and chosen pilots"),
        (POLICY_MEMBERS, "Every active member"),
    ]

    TOKEN_TYPE_CHOICES = [
        (t.value, t.value)
        for t in TokenType
        if t not in (TokenType.PUBLIC, TokenType.CAMPAIGN)
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
    roster_hidden = models.BooleanField(
        default=False,
        help_text=(
            "When set, only active members and people who manage this group "
            "see names and portraits. Everyone else sees a count of blurred "
            "placeholders."
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

    post_policy = models.CharField(
        max_length=16, choices=POLICY_CHOICES, default=POLICY_CHIEFS
    )
    fleet_policy = models.CharField(
        max_length=16, choices=POLICY_CHOICES, default=POLICY_CHIEFS
    )
    event_policy = models.CharField(
        max_length=16, choices=POLICY_CHOICES, default=POLICY_CHIEFS
    )
    post_publishers = models.ManyToManyField(
        "auth.User",
        blank=True,
        related_name="tribe_group_post_publisher_of",
        help_text="Chosen pilots who may post as the group.",
    )
    fleet_publishers = models.ManyToManyField(
        "auth.User",
        blank=True,
        related_name="tribe_group_fleet_publisher_of",
        help_text="Chosen pilots who may schedule group fleets.",
    )
    event_publishers = models.ManyToManyField(
        "auth.User",
        blank=True,
        related_name="tribe_group_event_publisher_of",
        help_text="Chosen pilots who may create group events.",
    )
    allow_alliance_posts = models.BooleanField(
        default=True,
        help_text="Off: every post published as the group is members only.",
    )
    allow_open_fleets = models.BooleanField(
        default=False,
        help_text="Publishers may open group fleets to the whole alliance.",
    )

    @property
    def effective_discord_channel_id(self) -> int | None:
        """The group's channel, or its tribe's when the group has none."""
        return self.discord_channel_id or self.tribe.discord_channel_id

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
